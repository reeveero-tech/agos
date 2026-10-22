"""R-W2-006 (ADR-0005) — خدمة تحليل المستودعات المشتركة: الخط الواحد.

خط واحد: مسح واحد يبني فهرس ملفات واحداً (مع المحتوى المقروء وسبب عدم القراءة)،
ثم مرحلة واحدة لإحصاءات اللغات (``stack_detection.language_weights`` — المصدر
الواحد) وكشف الأطر (``stack_detection.detect_stack``). كل مدخل قديم يفوّض إلى
هذه الخدمة ويُسقط النتيجة إلى شكله القديم بالضبط (تصنيفات الواجهات القديمة
إسقاطات صريحة فوق الفهرس الموحد — لا تُسقط صمتاً ولا يُقارن مقياسان مختلفان).

المصدران:
- ``analyze_url``: استنساخ عبر المزوّد القائم (سياسة المسح R-W2-004/005: المخفي
  ذو الصلة فقط، لا قراءة عبر الروابط، محتوى الملفات الصغيرة) — الحقائق تكتمل
  قبل أي تنظيف.
- ``analyze_path``: مجلد محلي مباشرة — بلا استنساخ ولا افتراضات git ولا شبكة،
  وبلا تخزين مؤقت (لا بصمة تغيّر معتمدة بعد — ADR-0005).

الملف الكبير أو الثنائي ليس ملفاً فارغاً: ``unread`` يوثق سبب عدم القراءة.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Optional

__all__ = [
    "FileEntry", "SharedAnalysis", "ScanPolicy", "RepositoryAnalysisService",
    "get_analysis_service",
]


# ---------------------------------------------------------------------------
# السياسات — تصنيفات الواجهات القديمة إسقاطات صريحة لا مسحاً مستقلاً لكل واجهة
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScanPolicy:
    """سياسة المسح: ماذا يُستثنى وكيف يُقرأ المحتوى.

    كل واجهة قديمة تحتفظ بسياستها القديمة بالضبط (G2) — التوحيد في المسح والفهرس
    والمراحل، لا في فرض سياسة واحدة على الجميع.
    """
    #: أسماء (ملفات/مجلدات) تُستثنى — callable يعيد True للاستثناء
    exclude: Callable[[str], bool] = lambda name: False
    #: سياسة المشي النووية (R-W2-004): المخفي ذو الصلة فقط يبقى (.github،
    #: .gitignore، ...) وما عداه مخفي يُستثنى (مع تقليم المجلدات لا مجرد تخطيها)،
    #: و.git يُستثنى دائماً، ولا قراءة عبر روابط رمزية.
    relevant_hidden_only: bool = False
    #: حد قراءة المحتوى بالبايتات (سياسة الواجهة القديمة نفسها)
    max_read_bytes: int = 1_000_000
    #: ملفات تُهشّ أثناء المسح نفسه (تدفقيًا بقراءة utf-8 صارمة كما في البصمة
    #: القديمة — فشل فك الترميز يعني تخطي الهاش كما كان، لا هاش محتوى بديل):
    #: يُخزّن في ``FileEntry.sha256``. الهاش من البايتات الخام = بايتات الملف
    #: نفسها للملفات الصالحة (وللصغيرة: من النص المُعاد ترميزه — ذات الشيء).
    hash_predicate: Optional[Callable[[str], bool]] = None
    #: تصنيف أسطر الملفات الكبيرة (>حد القراءة) تدفقياً — كانت مقاييس
    #: intelligence تقرؤها بلا حد؛ محلل الحضارة لم يكن يقرؤها فبقيت False
    #: عنده افتراضاً (سياسة القديم نفسها). الملف المُهشّ يُصنّف دائماً
    #: (المرور واحد — التصنيف مجاني مع الهاش).
    classify_big: bool = False


def civ_exclude(name: str) -> bool:
    """سياسة محلل الحضارة القديمة (repository_analysis) — كما هي بالضبط."""
    excluded_names = {
        '__pycache__', '.git', '.svn', '.hg', 'node_modules', 'venv', '.venv',
        'env', 'dist', 'build', '.egg-info', '.pytest_cache', '.tox', '.coverage',
        'htmlcov', '.mypy_cache', '.DS_Store', 'Thumbs.db', '.idea', '.vscode',
    }
    excluded_suffixes = ('.pyc', '.pyo')
    return name in excluded_names or name.endswith(excluded_suffixes)


CIV_SCAN_POLICY = ScanPolicy(exclude=civ_exclude)
"""سياسة مسح محلل الحضارة — الإسقاط القديم (يحصي JSON/YAML/Markdown لغاتٍ)."""

KERNEL_SCAN_POLICY = ScanPolicy(relevant_hidden_only=True)
"""سياسة مسح النواة (R-W2-004/005) — للمصدر URL."""


# ---------------------------------------------------------------------------
# النتيجة المشتركة
# ---------------------------------------------------------------------------

@dataclass
class FileEntry:
    """مدخل فهرس: الإحصاءات تُجمع مرة واحدة في المسح."""
    path: str = ""          # نسبي للجذر
    size_bytes: int = 0
    is_dir: bool = False
    extension: str = ""
    #: عدد أسطر **المحتوى المقروء** (دلالة قراءة النص القديمة: replace
    #: + توطين الأسطر) — فقط للملفات المخزّنة في ``contents``؛ -1 لغيرها.
    #: هذا عدّ أسطر اللغات (civ وintelligence كلاهما كان يقرأ replace).
    lines: int = -1
    #: عدد أسطر **مقاييس التصنيف** (فك ignore كما كانت مقاييس القديم
    #: تقرأ) — للملفات المصنّفة ولو لم تُقرأ محتوىً (الكبير/الثنائي)؛ -1
    #: لغير المصنّف. الشيفرة = metric_lines - comment - blank.
    metric_lines: int = -1
    #: أسطر التعليق/الفراغ (تصنيف فوق فك ignore). -1 = غير مصنّف
    comment_lines: int = -1
    blank_lines: int = -1
    #: هاش المحتوى للملفات المطابقة لسياسة الهاش (تدفقي أثناء المسح)
    sha256: str = ""


@dataclass
class SharedAnalysis:
    """الحقائق المشتركة الكاملة — تُجمع قبل أي تنظيف (ADR-0005).

    الإسقاطات (DNA النواة، RepositoryInfo الحضارة، جينوم intelligence، DNA‏ rie)
    دوالّ صرفة فوق هذه الحقائق: لا تعيد فتح مسار حُذف ولا تعيد مسحاً.
    """
    # مصدر التحليل — أحدهما فقط
    source_url: str = ""
    source_branch: str = ""
    source_commit: str = ""      # رأس الفرع (URL فقط) — مفتاح التخزين المؤقت
    source_path: str = ""

    # الفهرس والمحتوى
    files: List[FileEntry] = field(default_factory=list)
    contents: Dict[str, str] = field(default_factory=dict)   # path → محتوى مقروء
    unread: Dict[str, str] = field(default_factory=dict)     # path → سبب عدم القراءة
    #: أخطاء الوصول أثناء المسح نفسه — نقص مسمى لا نجاح صامت (ADR-0005)
    scan_errors: Dict[str, str] = field(default_factory=dict)

    # البيانات الوصفية (اسم/مالك) — DNA النواة يحتاجها
    meta: Dict[str, str] = field(default_factory=dict)

    # المراحل المشتركة (مصدر واحد: stack_detection)
    #: إحصاء لغات ملفات الشيفرة مرجّحاً بالأسطر (LanguageStat لكل لغة)
    code_languages: Dict[str, Any] = field(default_factory=dict)
    #: خريطة الملفات البيانية {مسار: محتوى أو None}
    manifests: Dict[str, Optional[str]] = field(default_factory=dict)
    #: تقرير المكدس الكامل (الأطر + الأدلة + بيئات التشغيل) — StackReport
    stack: Any = None

    @property
    def file_count(self) -> int:
        return sum(1 for f in self.files if not f.is_dir)

    @property
    def directory_count(self) -> int:
        return sum(1 for f in self.files if f.is_dir)

    @property
    def total_files(self) -> int:
        """عدد الملفات الكلي — إسقاط rie القديم (total_files)."""
        return self.file_count

    @property
    def commit(self) -> str:
        """الالتزام — إسقاط rie القديم (commit)."""
        return self.source_commit


# ---------------------------------------------------------------------------
# الماسح الواحد
# ---------------------------------------------------------------------------

# فواصل الأسطر بدلالة قراءة القديم النصية: وضع النص يوطّن \r\n/\r إلى \n
# ثم readlines تقسم على \n وحدها — لا \v/\f/... (ليست splitlines)
_LINE_TERMINATORS = __import__("re").compile("[\n\r]")


class _LineClassifier:
    """مصنّف سطر تراكمي — يحفظ بداية السطر الدالة وعلامات إغلاق التعليق
    بذاكرة ثابتة أياً كان طول السطر (لا تخزين السطر ولا اقتطاع دلالاته).

    القرار كما في القديم بالضبط: أول محرف غير فارغ يحدد — # أو // تعليق،
    و/* أو \"\"\" تعليق يفتح كتلة (سطر الافتتاح لا يغلقها — كما في القديم)،
    وسطر داخل كتلة تعليق أياً كانت بدايته (عدا العلامات أعلاه) تعليق
    يبحث عن علامة الإغلاق أينما وقعت في السطر، وما عداه شيفرة أو فراغ.
    """

    def __init__(self, state: dict):
        self.state = state
        self.pending = ""    # بداية السطر حتى القرار (≤ 3 محارف بعد الفراغ)
        self.decided = None  # None / "comment" / "code"
        self.block_at_start = bool(state.get("in_block"))
        self.scan_close = False   # السطر داخل كتلة: ابحث عن علامة الإغلاق
        self.carry = ""      # آخر محرفين لعلامات الإغلاق عبر حدود الأجزاء
        self.started = False  # وصلت أجزاء لهذا السطر (ولو فراغاً)

    def feed(self, fragment: str) -> None:
        """تغذية جزء من السطر الحالي (بلا فواصل) — الجزء محدود والذاكرة ثابتة."""
        self.started = True
        if self.decided is not None:
            self._scan(fragment)
            return
        # القرار: أول محرف غير فارغ (الفراغ يُستهلك بلا تخزين)
        self.pending = (self.pending + fragment).lstrip()
        if not self.pending:
            return  # لم تظهر بداية بعد — قد يكون سطر فراغ
        first = self.pending[0]
        consumed = 1   # عدد محارف البداية التي اتُّخذ منها القرار
        if first == "#":
            self.decided = "comment"
        elif first == "/":
            if len(self.pending) < 2:
                return  # انتظر المحرف الثاني
            if self.pending[1] == "/":
                self.decided = "comment"
                consumed = 2
            elif self.pending[1] == "*":
                self.decided = "comment"
                self.state["in_block"] = True
                self.scan_close = False  # سطر الافتتاح لا يغلق (كما في القديم)
                consumed = 2
            else:
                self._decide_code_or_block()
        elif first == '"':
            if len(self.pending) < 3:
                return  # انتظر الثلاثة (بداية كتلة نصية)
            if self.pending[:3] == '"""':
                self.decided = "comment"
                self.state["in_block"] = True
                self.scan_close = False
                consumed = 3
            else:
                self._decide_code_or_block()
        else:
            self._decide_code_or_block()
        # ما تبقى بعد قرار البداية — عند فحص الإغلاق يُمرّر الجزء **كاملاً**
        # (العلامة قد تعتلي حد القرار نفسه: "*/" تبدأ بالمحرف المُستهلك)،
        # وأولوية القديم محفوظة: سطر الافتتاح و# و// لا تفحص (scan_close=False)
        full = self.pending
        self.pending = ""
        if full:
            self._scan(full)

    def _decide_code_or_block(self) -> None:
        if self.block_at_start:
            # سطر داخل كتلة تعليق: تعليق + ابحث عن الإغلاق أينما وقع
            self.decided = "comment"
            self.scan_close = True
        else:
            self.decided = "code"

    def _scan(self, fragment: str) -> None:
        if not self.scan_close:
            return  # بقية السطر غير دالة — تُستهلك بلا تخزين
        text = self.carry + fragment
        if '"""' in text or "*/" in text:
            self.state["in_block"] = False
            self.scan_close = False
        self.carry = text[-2:]

    def end(self) -> None:
        """نهاية السطر (فاصل أو نهاية ملف) — الاحتساب ثم التهيئة للسطر التالي."""
        if self.decided is None and self.pending:
            # بداية غير مكتملة عند نهاية السطر — قرار بما ظهر
            if (self.pending.startswith("#") or self.pending.startswith("//")
                    or self.pending.startswith("/*")
                    or self.pending.startswith('"""')):
                self.decided = "comment"
            else:
                self._decide_code_or_block()
            # وفحص الإغلاق فوق الجزء كاملاً إن كان السطر داخل كتلة
            full, self.pending = self.pending, ""
            if full:
                self._scan(full)
        if self.decided == "comment":
            self.state["comment"] += 1
        elif self.decided == "code":
            self.state["code"] += 1
        else:
            self.state["blank"] += 1
        # تهيئة السطر التالي
        self.decided = None
        self.pending = ""
        self.block_at_start = bool(self.state.get("in_block"))
        self.scan_close = False
        self.carry = ""
        self.started = False


class _MetricsClassifier:
    """تصنيف مقاييس تدفقي فوق نص مفكّك — دلالات قراءة القديم النصية بالضبط:
    توطين \r\n/\r إلى \n ثم تقسيم readlines على \n، بذاكرة ثابتة (أجزاء
    الأسطر لا تُخزّن — المصنّف التراكمي يقرر من بداية السطر وعلامات الإغلاق)."""

    def __init__(self):
        self.state = {"comment": 0, "blank": 0, "code": 0, "in_block": False}
        self.count = 0
        self._line = _LineClassifier(self.state)
        self._cr_pending = False

    def feed(self, text: str) -> None:
        i, n = 0, len(text)
        while i < n:
            if self._cr_pending:
                # \r آخر دفقة: إن تبعتها \n فهما فاصل واحد
                self._cr_pending = False
                if text[i] == "\n":
                    i += 1
                self._end_line()
                continue
            m = _LINE_TERMINATORS.search(text, i)
            if m is None:
                self._line.feed(text[i:])
                return
            self._line.feed(text[i:m.start()])
            if m.group() == "\n":
                i = m.end()
                self._end_line()
            elif m.end() == n:
                self._cr_pending = True   # قد تتبعها \n في الدفقة التالية
                return
            else:
                i = m.end() + (1 if text[m.end()] == "\n" else 0)
                self._end_line()

    def close(self) -> None:
        if self._cr_pending:
            self._cr_pending = False
            self._end_line()
        elif self._line.started:
            self._end_line()   # آخر سطر بلا فاصل — سطر (كما في readlines)

    def _end_line(self) -> None:
        self._line.end()
        self.count += 1


def _classify_lines(text: str) -> tuple:
    """تصنيف أسطر الشيفرة/التعليق/الفراغ — دلالات قراءة المقاييس القديمة
    نفسها (توطين \r\n/\r ثم readlines) — والمصنّف التراكمي نفسه للمسار
    التدفقي وللملفات الصغيرة (دلالات واحدة)."""
    mc = _MetricsClassifier()
    mc.feed(text)
    mc.close()
    return mc.count, mc.state["comment"], mc.state["blank"]


def search_keywords(full_path: str, patterns: dict) -> set:
    """بحث تدفقي بدفعات ثابتة الذاكرة (64KB + تداخل حدود الكلمات) — لا سقف
    قراءة ولا تحميل كامل في الذاكرة، ولا فتح روابط رمزية (R-W2-005).
    المطابقات محفوظة عبر حدود الدفعات (تداخل بطول أطول كلمة − 1)، والفك
    بمفكّك تزايدي فلا يسقط محرف UTF-8 صحيح انقسم بين دفعتين."""
    import codecs
    if os.path.islink(full_path):
        return set()
    keywords = [k for kws in patterns.values() for k in kws]
    if not keywords:
        return set()
    overlap = max(len(k) for k in keywords) - 1
    decoder = codecs.getincrementaldecoder("utf-8")("ignore")
    found = set()
    carry = ""
    try:
        with open(full_path, "rb") as fh:
            while True:
                chunk = fh.read(1 << 16)
                if not chunk:
                    break
                text = carry + decoder.decode(chunk)
                low = text.lower()
                for name, kws in patterns.items():
                    if any(k in low for k in kws):
                        found.add(name)
                carry = text[-overlap:] if overlap > 0 else ""
    except OSError:
        return set()
    return found


def _scan_big_file(full_path: str, entry: "FileEntry", want_hash: bool) -> None:
    """مرور تدفقي واحد للملف الكبير: هاش نصّي مطابق للقديم + تصنيف أسطر — بلا
    تحميل كامل في الذاكرة.

    **الهاش مطابق للقديم بالضبط**: فك utf-8 صارم تدفقي، ثم توطين الأسطر
    كما في وضع النص (CRLF/CR → LF) — تماماً كقراءة ``fh.read()`` النصية
    القديمة — ثم هاش النص المُعاد ترميزه (فاقد الترميز يُرفض الهاش كاملاً
    كما كانت البصمة تتخطاه). **والتصنيف فوق فك ignore** كما كانت مقاييس
    القديم تقرأ (``errors='ignore'``). الملف المُهشّ يُصنّف دائماً — المرور
    واحد والتصنيف مجاني مع الهاش.
    """
    import codecs
    h = hashlib.sha256()
    dec_strict = codecs.getincrementaldecoder("utf-8")()
    dec_ignore = codecs.getincrementaldecoder("utf-8")("ignore")
    strict_ok = True
    pending = ""   # حرف CR معلّق قد يكتمل CRLF في الدفقة التالية
    mc = _MetricsClassifier()   # دلالات قراءة المقاييس القديمة — بذاكرة ثابتة
    try:
        with open(full_path, "rb") as fh:
            while True:
                chunk = fh.read(1 << 16)
                if not chunk:
                    break
                if want_hash and strict_ok:
                    try:
                        text = dec_strict.decode(chunk)
                    except UnicodeDecodeError:
                        strict_ok = False
                    else:
                        pending += text
                        # لا تُطبّع سطراً قد يكتمل CRLF في الدفقة التالية
                        if pending.endswith("\r"):
                            ready, pending = pending[:-1], "\r"
                        else:
                            ready, pending = pending, ""
                        if ready:
                            h.update(ready.replace("\r\n", "\n")
                                     .replace("\r", "\n").encode("utf-8"))
                # التصنيف فوق فك ignore — المصنّف التراكمي (بلا تخزين الأسطر)
                mc.feed(dec_ignore.decode(chunk))
        mc.close()
    except OSError:
        return  # فشل القراءة: يبقى غير مصنّف (كما في القديم)
    entry.metric_lines = mc.count
    entry.comment_lines = mc.state["comment"]
    entry.blank_lines = mc.state["blank"]
    if want_hash:
        try:
            tail = dec_strict.decode(b"", True)
        except UnicodeDecodeError:
            strict_ok = False
            tail = ""
        if strict_ok:
            # المعلّق الأخير: CR وحيدة = سطر منتهٍ (توطين النص)
            pending += tail
            h.update(pending.replace("\r\n", "\n")
                     .replace("\r", "\n").encode("utf-8"))
        entry.sha256 = h.hexdigest()[:8] if strict_ok else ""


def scan_tree(root: Path, policy: ScanPolicy) -> tuple:
    """مسح واحد: يعيد (الملفات، المحتويات، غير المقروء، أخطاء المسح) وفق السياسة.

    سياسة القراءة: الملف الصغير نصياً يُقرأ ويُعدّ أسطره؛ الكبير/الثنائي يُوثق
    سبب عدم قراءته في ``unread`` — وليس ملفاً فارغاً. أسطر التعليق/الفراغ
    تصنّف تدفقياً للجميع (إحصاءة واحدة — الكبير بلا تحميل كامل في الذاكرة).
    ملفات سياسة الهاش تُقرأ utf-8 صارمة وتُهشّ أثناء المسح (فاقد فك الترميز
    يُتخطى كما في البصمة القديمة). أخطاء الوصول تُسجّل في ``scan_errors``
    لا أن تُبلع صمتاً.
    """
    files: List[FileEntry] = []
    contents: Dict[str, str] = {}
    unread: Dict[str, str] = {}
    scan_errors: Dict[str, str] = {}
    max_read = policy.max_read_bytes
    hash_predicate = policy.hash_predicate

    def is_relevant_hidden(rel: str) -> bool:
        from stack_detection import is_relevant_hidden as _irh
        return _irh(rel)

    def on_walk_error(err: OSError) -> None:
        # نقص مسمى — لا نجاح صامت بنصف فهرس (ADR-0005)
        scan_errors[getattr(err, "filename", "")] = (
            type(err).__name__ + (f": {err.strerror}" if getattr(err, "strerror", None) else ""))

    for dirpath, dirnames, filenames in os.walk(root, onerror=on_walk_error):
        # .git يُستثنى دائماً (جزء مسار دقيق — .github يبقى)
        if any(part == ".git" for part in PurePosixPath(dirpath).parts):
            continue
        rel_dir = os.path.relpath(dirpath, root)

        if policy.relevant_hidden_only:
            # تقليم لا تخطي: المجلد المخفي غير ذي الصلة لا يساهم ملفاته
            dirnames[:] = [d for d in dirnames
                           if not (d.startswith(".") and not is_relevant_hidden(
                               os.path.join(rel_dir, d) if rel_dir != "." else d))]
        else:
            dirnames[:] = [d for d in dirnames if not policy.exclude(d)]

        for dirname in dirnames:
            dir_path = os.path.join(rel_dir, dirname) if rel_dir != "." else dirname
            files.append(FileEntry(path=dir_path, is_dir=True))

        for filename in filenames:
            if policy.relevant_hidden_only:
                if filename.startswith(".") and not is_relevant_hidden(
                        os.path.join(rel_dir, filename) if rel_dir != "." else filename):
                    continue
            elif policy.exclude(filename):
                continue
            full_path = os.path.join(dirpath, filename)
            file_path = os.path.join(rel_dir, filename) if rel_dir != "." else filename

            # R-W2-005: لا قراءة عبر رابط رمزي قد يحلّ خارج الجذر
            if os.path.islink(full_path):
                files.append(FileEntry(path=file_path, extension=Path(filename).suffix,
                                       size_bytes=0))
                unread[file_path] = "symlink"
                continue

            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = 0
            entry = FileEntry(path=file_path, size_bytes=size,
                              extension=Path(filename).suffix)

            # ملفات سياسة الهاش الصغيرة: قراءة نصية صارمة كاملة (كما في البصمة
            # القديمة) — فشلها يعني هاشاً فارغاً لا قراءة بديلة للمحتوى
            want_hash = hash_predicate is not None and hash_predicate(filename)
            if want_hash and size <= max_read:
                try:
                    with open(full_path, "r", encoding="utf-8") as fh:
                        text = fh.read()
                    entry.sha256 = hashlib.sha256(text.encode()).hexdigest()[:8]
                except (OSError, ValueError, UnicodeDecodeError):
                    entry.sha256 = ""

            if size > max_read:
                unread[file_path] = "too_large"
                # المُهشّ يُصنّف دائماً (مرور واحد)؛ وغير المُهشّ عند طلب
                # سياسة تصنيف الكبير (مقاييس intelligence كانت تقرؤه بلا حد)
                if want_hash or policy.classify_big:
                    _scan_big_file(full_path, entry, want_hash)
            else:
                try:
                    # قراءات من البايتات نفسها — كل بدلالة قارئها القديم:
                    # replace للمحتوى المقروء وأسطر اللغات (كما كانت قراءات
                    # الحضارة/النواة/intelligence للغات)، وignore لمقاييس
                    # التصنيف (كما كانت مقاييس intelligence تقرأ)
                    with open(full_path, "rb") as fh:
                        raw = fh.read()
                    ignored = raw.decode("utf-8", "ignore")
                    replaced = raw.decode("utf-8", "replace")
                    if "\x00" in replaced:
                        unread[file_path] = "binary"
                        # مقاييس فقط — تصنيف فوق فك ignore (كما كانت المقاييس
                        # تعدّ الثنائي)؛ لا محتوى ولا أسطر لغات (كما في القديم)
                        (entry.metric_lines, entry.comment_lines,
                         entry.blank_lines) = _classify_lines(ignored)
                    else:
                        # المحتوى المخزّن مُطبّع الأسطر كما كانت القراءة النصية
                        # القديمة (CRLF/CR → LF) — لا CRLF خاماً يصل الكاشفين
                        norm = replaced.replace("\r\n", "\n").replace("\r", "\n")
                        contents[file_path] = norm
                        # أسطر المحتوى — معادلة القديم نفسها: عدّ \n
                        entry.lines = ((norm.count("\n")
                                         + (0 if norm.endswith("\n") else 1))
                                        if norm else 0)
                        # ومقاييس التصنيف فوق فك ignore
                        (entry.metric_lines, entry.comment_lines,
                         entry.blank_lines) = _classify_lines(ignored)
                except (OSError, ValueError):
                    unread[file_path] = "read_error"
            files.append(entry)

    return files, contents, unread, scan_errors


# ---------------------------------------------------------------------------
# الخدمة
# ---------------------------------------------------------------------------

class RepositoryAnalysisService:
    """الخط الواحد لتحليل المستودعات (ADR-0005) — تفوّض إليه كل الواجهات القديمة."""

    def analyze_url(self, url: str, branch: str = "main") -> SharedAnalysis:
        """التحليل من URL: استنساخ وقراءة عبر المزوّد القائم (سياسة R-W2-004/005
        نفسها — بما فيها البيانات الوصفية) ثم المراحل المشتركة.

        الحقائق تكتمل في ``SharedAnalysis`` قبل تنظيف المستودع المستنسخ
        (المحتوى محفوظ في الذاكرة — لا يحتاج الإسقاط المسار بعدها).
        """
        from providers import LocalRepositoryProvider, ReadRepositoryInput

        provider = LocalRepositoryProvider()
        from capabilities import RepositoryAnalysisInput
        print(f"[CAPABILITY] Cloning {url}")
        clone_result = provider._clone(RepositoryAnalysisInput(url, branch))
        repo_path = clone_result.path
        try:
            print("[CAPABILITY] Reading repository")
            read_result = provider._read(ReadRepositoryInput(repo_path))
            snapshot = read_result.snapshot
            print("[CAPABILITY] Detecting languages")
            print("[CAPABILITY] Detecting frameworks")
            files: List[FileEntry] = []
            contents: Dict[str, str] = {}
            unread: Dict[str, str] = {}
            for node in snapshot.files:
                entry = FileEntry(
                    path=node.path, is_dir=node.is_dir,
                    size_bytes=getattr(node, "size", 0) or 0,
                    extension=Path(node.path).suffix)
                if not node.is_dir:
                    if node.content is None:
                        unread[node.path] = "not_read"
                    else:
                        contents[node.path] = node.content
                        entry.lines = (node.content.count("\n")
                                       + (0 if node.content.endswith("\n")
                                          or not node.content else 1))
                files.append(entry)
            meta = {
                "name": snapshot.metadata.name,
                "url": snapshot.metadata.url,
                "owner": snapshot.metadata.owner,
            }
            return self._finish(
                files, contents, unread,
                source_url=url,
                source_branch=self._actual_branch(repo_path) or branch,
                source_commit=self._local_revision(repo_path),
                meta=meta,
            )
        finally:
            if os.path.exists(repo_path):
                parent = os.path.dirname(repo_path)
                if os.path.exists(parent):
                    shutil.rmtree(parent, ignore_errors=True)

    def analyze_path(self, path: str, policy: Optional[ScanPolicy] = None) -> SharedAnalysis:
        """التحليل من مجلد محلي: بلا استنساخ ولا شبكة ولا افتراضات git.

        ``policy``: سياسة الواجهة القديمة نفسها (افتراضياً سياسة محلل الحضارة).
        بلا تخزين مؤقت — لا بصمة تغيّر معتمدة بعد (ADR-0005).
        """
        root = Path(path).resolve()
        if not root.exists():
            raise ValueError(f"Repository path does not exist: {root}")
        if not root.is_dir():
            raise ValueError(f"Repository path is not a directory: {root}")

        files, contents, unread, scan_errors = scan_tree(root, policy or CIV_SCAN_POLICY)
        # نقص معلن لا نجاح صامت: أخطاء الوصول أثناء المسح تُعلن من الخدمة
        # نفسها — كل واجهة فوقها (محلل الحضارة، بصمتها، المنظّم، intelligence)
        # ترث الإعلان تلقائياً (ADR-0005)
        if scan_errors:
            import warnings
            warnings.warn(
                "repository scan gaps (access errors): "
                + "; ".join(f"{p}: {r}" for p, r in sorted(scan_errors.items())),
                stacklevel=2)
        return self._finish(
            files, contents, unread,
            source_path=str(root),
            meta={"name": root.name, "url": "", "owner": ""},
            root=root,
            scan_errors=scan_errors,
        )

    # -- المراحل المشتركة ---------------------------------------------------

    def _finish(self, files, contents, unread, *, source_url="", source_branch="",
                source_commit="", source_path="", meta=None, root=None,
                scan_errors=None) -> SharedAnalysis:
        """مرحلة واحدة للجميع: إحصاء اللغات وكشف المكدس من الفهرس والمحتوى.

        إحصاء اللغات فوق **الفهرس الكامل** (غير المقروء بقيمة None كما في
        المسار القديم تماماً) — لا فوق المقروء وحده، فلا تختفي لغة لمجرد أن
        ملفها الكبير لم يُقرأ.
        """
        from stack_detection import detect_stack, is_manifest, language_weights

        # إحصاء لغات ملفات الشيفرة — المصدر الواحد (مرجّح بالأسطر)؛ الفهرس
        # الكامل مع None لغير المقروء (دلالات المسار القديم)
        full_index = {f.path: contents.get(f.path)
                      for f in files if not f.is_dir}
        code_languages = language_weights(full_index)
        # الملفات البيانية — منها تقرير المكدس الكامل (الأطر + الأدلة + البيئات)؛
        # غير المقروء يُدرج بقيمة None كما في المسار القديم تماماً
        manifests = {p: full_index[p] for p in full_index if is_manifest(p)}
        stack = detect_stack(manifests)

        return SharedAnalysis(
            source_url=source_url, source_branch=source_branch,
            source_commit=source_commit, source_path=source_path,
            files=files, contents=contents, unread=unread,
            scan_errors=scan_errors or {},
            meta=meta or {}, code_languages=code_languages,
            manifests=manifests, stack=stack,
        )

    # -- مساعدات ------------------------------------------------------------

    @staticmethod
    def _local_revision(repo_path: str) -> str:
        """رأس HEAD للمستودع المستنسخ (لسلاسل rie وDNA النواة)."""
        import subprocess
        try:
            out = subprocess.run(["git", "-C", repo_path, "rev-parse", "HEAD"],
                                 capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return ""
        return out.stdout.strip() if out.returncode == 0 else ""

    @staticmethod
    def _actual_branch(repo_path: str) -> str:
        """الفرع الفعلي بعد الاستنساخ — يعكس تراجع clone_safety إلى الفرع
        الافتراضي إن لم يوجد المطلوب (البيانات تعكس الواقع لا المعامل)."""
        import subprocess
        try:
            out = subprocess.run(
                ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return ""
        branch = out.stdout.strip() if out.returncode == 0 else ""
        return "" if branch == "HEAD" else branch


_service: Optional[RepositoryAnalysisService] = None


def get_analysis_service() -> RepositoryAnalysisService:
    """الخدمة المشتركة — بلا حالة تُذكر، مفردة بسيطة لاتساق نقاط الدخول."""
    global _service
    if _service is None:
        _service = RepositoryAnalysisService()
    return _service
