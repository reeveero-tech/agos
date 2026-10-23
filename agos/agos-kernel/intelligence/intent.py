# -*- coding: utf-8 -*-
"""تفسير النية (R-W1-006): طلب طبيعي → نية منظمة → مواصفة مهمة.

العقد المعلن — آلية محدودة معلنة لا مفسر قصد حر:

- **معجم ثنائي اللغة معلن:** كل مفهوم له مصطلحات سطحية (عربية وإنجليزية)
  معلنة في ``CONCEPT_TERMS`` — لا تخمين معجمي خارج الجدول.
- **تجريد سلفي عربي معلن ومحدود:** بادئات (ال، و) ولاحقات الملكية
  (ه، ها، ك، ي، نا، كم، هم، هن، هما) تُحلّ عن الرموز قبل المطابقة —
  «أطره» و«اعتمادياته» تطابقان «أطر» و«اعتماديات».
- **جدول إيفاء معلن ومُثبت بالمخرجات:** كل مفهوم يُوفَّى بقدرةٍ **يحمل
  مخرجها الفعلي** حقيقته (حقل مخرج أو حقيقة مخرج) — لا وصفاً ولا مهارة:
  ``RepositoryDNA`` يحمل ``frameworks/dependencies/languages/license/config_files``
  (حقول معلنة في العقد)، وRPP يحملها حقائق سمات في ``universal_repository_object``.
  اختبار التأسيس يثبت أن الحقول المزعومة موجودة فعلاً في الكود (لا انجراف).
- **ترتيب الإيفاء المعلن:** قدرة **مخصصة** (مخرجها كله هو المفهوم — مثل
  SecurityScan للأمن) تسبق قدرة **عرضية** (تحمل المفهوم حقلاً بين حقول —
  مثل DNA.license). التعادل بين المرتبة الأولى بعد الترتيب → غموض مسمّى.
- **النفي:** رمز نفي يسبق مصطلح المفهوم مباشرةً يستبعد المفهوم من المطلوب —
  لا يُطلب ما نُفي.
- **الاستفهام:** أدوات الاستفهام المعرفة تسمّي الطلب سؤالاً — لا يُعامل سؤال
  كأمر تنفيذ (فشل مسمّى لا تنفيذ).
- **لا تخمين معاملات:** المصادر (رابط/مسار) تُستخرج نصياً فقط؛ ما لم يُذكر
  (فرع/عمق/…) لا يُخمَّن — القدرة تعاملها بقيمها المعلنة.
- **المدخل المطلوب الغائب:** المرشح الفائز يحتاج مصدر مستودع ولم يُذكر في
  النص → فجوة مسماة لا اختلاق معامل.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# المفاهيم ومصطلحاتها السطحية (معجم ثنائي معلن — لا مصدر آخر)
# ---------------------------------------------------------------------------
CONCEPT_TERMS: Dict[str, List[str]] = {
    # مفاهيم المخرجات المطلوبة
    "frameworks": ["الأطر", "أطر", "إطار", "اطار", "frameworks", "framework"],
    "dependencies": ["الاعتماديات", "اعتماديات", "اعتمادية", "التبعيات",
                     "تبعيات", "dependencies", "dependency"],
    "languages": ["اللغات", "لغات", "لغة", "languages", "language"],
    "dna": ["البصمة", "بصمة", "dna"],
    "security": ["الأمن", "أمن", "الأمان", "أمان", "الثغرات", "ثغرات",
                 "security", "vulnerabilities"],
    "license": ["الرخصة", "رخصة", "الرخص", "رخص", "التراخيص", "تراخيص",
                "license"],
    "configuration": ["التهيئة", "تهيئة", "الإعدادات", "إعدادات",
                      "configuration"],
    "documentation": ["التوثيق", "توثيق", "documentation"],
    "infrastructure": ["البنية التحتية", "بنية تحتية", "infrastructure"],
    "genome": ["الجينوم", "جينوم", "genome"],
    "engineering-knowledge": ["المعرفة الهندسية", "معرفة هندسية",
                              "engineering knowledge"],
    # مفهوم الفعل: تحليل/فحص مستودع
    "repository-analysis": ["حلل", "حلّل", "تحليل", "فحص", "افحص", "analyze",
                            "analysis", "scan"],
}

#: مصطلحات المستودع (تُستخدم لاستنتاج أن المصدر مطلوب — لا تُقترح قدرة)
_REPOSITORY_TERMS = ["مستودع", "المستودع", "repository", "repo"]

# ---------------------------------------------------------------------------
# جدول الإيفاء: مفهوم → قدرة → (حامل الإثبات في المخرج الفعلي، مخصص؟)
# مخصص = مخرج القدرة كله هو المفهوم؛ عرضي = المفهوم حقل/حقيقة بين حقول أخرى.
# ---------------------------------------------------------------------------
FULFILLMENT: Dict[str, Dict[str, Tuple[List[str], bool]]] = {
    "frameworks": {
        "RepositoryAnalysis": (["RepositoryDNA.frameworks"], False),
        "RepositoryDNAGeneration": (["RepositoryDNA.frameworks"], False),
        "RepositoryProcessingPipeline": (
            ["universal_repository_object.frameworks"], False),
    },
    "dependencies": {
        "RepositoryAnalysis": (["RepositoryDNA.dependencies"], False),
        "RepositoryProcessingPipeline": (
            ["universal_repository_object.dependencies"], False),
    },
    "languages": {
        "RepositoryAnalysis": (["RepositoryDNA.languages"], False),
        "RepositoryDNAGeneration": (["مخرج dict: languages/language_stats"], False),
        "RepositoryProcessingPipeline": (
            ["universal_repository_object.all_languages"], False),
    },
    "dna": {
        "RepositoryAnalysis": (["RepositoryDNA (كائن المخرج)"], True),
        "RepositoryDNAGeneration": (["RepositoryDNA (كائن المخرج)"], True),
    },
    "security": {
        "SecurityScan": (["مخرج المسح كله (تقرير الأمن)"], True),
    },
    "license": {
        "LicenseAnalysis": (["مخرج التحليل كله (رخصة SPDX)"], True),
        "RepositoryAnalysis": (["RepositoryDNA.license"], False),
    },
    "configuration": {
        "ConfigurationAnalysis": (["مخرج التحليل كله (ملفات التهيئة)"], True),
        "RepositoryAnalysis": (["RepositoryDNA.config_files"], False),
    },
    "documentation": {
        "DocumentationAnalysis": (["مخرج القياس كله (تغطية التوثيق)"], True),
    },
    "infrastructure": {
        "InfrastructureAnalysis": (["مخرج الكشف كله (Docker/K8s/Terraform)"],
                                  True),
    },
    "genome": {
        "CapabilityGenome": (["مخرج التقرير كله (جينوم القدرات)"], True),
    },
    "engineering-knowledge": {
        "EngineeringKnowledgeExtraction": (
            ["مخرج الاستخلاص كله (نتائج موثقة)"], True),
    },
    "repository-analysis": {
        # كل قدرة تستهلك مصدر مستودع — مخرجها كله تحليل للمستودع (مخصص)
        "RepositoryAnalysis": (["RepositoryDNA (كائن المخرج)"], True),
        "RepositoryDNAGeneration": (["RepositoryDNA (كائن المخرج)"], True),
        "RepositoryProcessingPipeline": (["uro (كائن المخرج)"], True),
        "SecurityScan": (["مخرج المسح كله"], True),
        "LicenseAnalysis": (["مخرج التحليل كله"], True),
        "ConfigurationAnalysis": (["مخرج التحليل كله"], True),
        "DocumentationAnalysis": (["مخرج القياس كله"], True),
        "InfrastructureAnalysis": (["مخرج الكشف كله"], True),
        "CapabilityGenome": (["مخرج التقرير كله"], True),
    },
}

#: القدرات التي تستهلك مصدر مستودع (رابط/مسار) في معاملاتها
NEEDS_REPOSITORY_SOURCE = {
    "RepositoryAnalysis", "RepositoryDNAGeneration",
    "RepositoryProcessingPipeline", "SecurityScan", "LicenseAnalysis",
    "ConfigurationAnalysis", "DocumentationAnalysis", "InfrastructureAnalysis",
    "CapabilityGenome",
}

#: مفهوم الفعل: تحليل/فحص مستودع
CONCEPT_SKILLS: Dict[str, List[str]] = {
    # جدول معلن مؤسس على عقود السجل الحي: مهارات مُوفِيي المفهوم الفعليين
    # (RDNG مُوفٍ للبصمة ولا يطلب GenerateDNA — الجدول تبعية المُوفِين لا
    # قدرة بعينها؛ يُختبر التأسيس)
    "repository-analysis": ["CloneRepository", "ReadRepository"],
    "dna": ["CloneRepository", "ReadRepository"],
}


def derived_skills(interpretation: "IntentInterpretation") -> List[str]:
    """المهارات المشتقة من المفاهيم المطلوبة — جدول معلن (CONCEPT_SKILLS)
    لا استخراج حر؛ المفهوم بلا تعيين مهاري لا يضيف شيئاً (مفاهيم المخرجات
    إيفاؤها بالحقول لا بالمهارات)."""
    skills: List[str] = []
    for concept in interpretation.required_concepts:
        for skill in CONCEPT_SKILLS.get(concept, []):
            if skill not in skills:
                skills.append(skill)
    return skills


#: نوافي الاستثناء — نطاقها الاسم التالي مباشرةً (بدون/بلا/غير): استثناء
#: مسمّى محدود النطاق
EXCLUDING_NEGATION_MARKERS = ("بدون", "بلا", "غير")
#: نفي فعلي — نطاقه الجملة/الطلب كله (لا/ليس): لا يمكن حسم نطاقه بآلية
#: محدودة، فالطلب المنفي لا يُنفَّذ (غموض مسمّى صفر تنفيذ)
VERBAL_NEGATION_MARKERS = ("لا", "ليس")
NEGATION_MARKERS = EXCLUDING_NEGATION_MARKERS + VERBAL_NEGATION_MARKERS

INTERROGATIVE_STARTERS = ("هل", "كيف", "لماذا", "أين", "متى", "ما هو",
                          "what", "how", "why", "can you", "could you")

_URL_RE = re.compile(r"https?://[^\s،؟]+")
_PATH_RE = re.compile(r"(?:^|\s)((?:/|\./)[^\s،؟]+)")

#: لاحقات الملكية العربية المعلنة (تُحلّ عن نهاية الرمز)
_POSSISSIVE_SUFFIXES = ("هما", "هؤلاء", "كما", "هنا", "هما", "هم", "هن", "كم",
                       "نا", "ها", "ه", "ك", "ي")
#: بادئات معرفة معلنة (تُحلّ عن بداية الرمز)
_ARTICLE_PREFIXES = ("ال",)
_CONJUNCTION_PREFIXES = ("و", "ف", "ب", "ل", "ك")


def _strip_clitics(tok: str) -> str:
    """تجريد سلفي عربي معلن ومحدود: بادئات التعريف/العطف ولاحقات الملكية.
    يُطبق على الرموز الطويلة فقط (≥3) فلا يأكل «لا» النافية ولا حروف الجر."""
    if len(tok) < 3:
        return tok
    for suf in _POSSISSIVE_SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 2:
            tok = tok[:-len(suf)]
            break
    for pref in _CONJUNCTION_PREFIXES:
        if tok.startswith(pref) and len(tok) - 1 >= 3:
            tok = tok[1:]
            break
    for pref in _ARTICLE_PREFIXES:
        if tok.startswith(pref) and len(tok) - 2 >= 2:
            tok = tok[2:]
            break
    return tok


@dataclass
class IntentInterpretation:
    """نية منظمة من طلب طبيعي — كل حقل بدليله (لا اختلاق)."""
    required_concepts: List[str] = field(default_factory=list)
    negated_concepts: List[str] = field(default_factory=list)
    is_repository_request: bool = False
    artifacts: Dict[str, str] = field(default_factory=dict)   # url فقط إن وُجد
    interrogative: bool = False
    #: نفي فعلي (لا/ليس) — نطاقه الجملة كله ولا آلية محدودة تحسمه: الطلب
    #: لا يُنفَّذ (غموض مسمّى)، والمنفيات قيود لا متطلبات محذوفة فقط
    verbal_negation: bool = False
    matched_terms: List[Tuple[str, str]] = field(default_factory=list)  # (مفهوم، مصطلح)


def _normalize(text: str) -> str:
    """تسوية معلنة: تشكيل/تطويل/همزات/ة-ه/ى-ي + أسطرة + إزالة ترقيم."""
    text = text.replace("ـ", "")            # التطويل
    for mark in ("َ", "ُ", "ِ", "ْ", "ّ", "ً", "ٌ", "ٍ"):
        text = text.replace(mark, "")       # التشكيل
    text = (text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
                .replace("ة", "ه").replace("ى", "ي"))
    return " ".join(text.lower().split())


def _tokens(normalized: str) -> List[str]:
    return [t for t in re.split(r"[\s،,.:؛;()]+", normalized) if t]


def _stripped_tokens(toks: List[str]) -> List[str]:
    return [_strip_clitics(t) for t in toks]


def interpret(text: str) -> IntentInterpretation:
    """تفسير طلب طبيعي → نية منظمة. كل قرار هنا قابل للعكس بالدليل."""
    normalized = _normalize(text or "")
    out = IntentInterpretation()
    out.interrogative = (
        normalized.startswith(INTERROGATIVE_STARTERS)
        or normalized.rstrip().endswith(("؟", "?")))
    toks = _tokens(normalized)
    stoks = _stripped_tokens(toks)
    out.verbal_negation = any(t in VERBAL_NEGATION_MARKERS for t in toks)
    negation_tokens = {_normalize(m) for m in EXCLUDING_NEGATION_MARKERS}
    for concept, terms in CONCEPT_TERMS.items():
        hit = None
        for term in terms:
            norm_term = _normalize(term)
            phrase = norm_term.split()
            if len(phrase) > 1:
                if _contains_phrase(stoks, phrase):
                    hit = term
                    break
            elif _strip_clitics(norm_term) in stoks:
                hit = term
                break
        if hit is None:
            continue
        idx = _term_index(stoks, _normalize(hit))
        # النفي المعلن: رمز نفي في الرمزين السابقين لموضع المصطلح
        negated = idx is not None and any(
            idx - k >= 0 and toks[idx - k] in negation_tokens
            for k in (1, 2))
        if negated:
            out.negated_concepts.append(concept)
        else:
            out.required_concepts.append(concept)
        out.matched_terms.append((concept, hit))
    if any(_normalize(t) in toks or _strip_clitics(_normalize(t)) in stoks
           for t in _REPOSITORY_TERMS):
        out.is_repository_request = True
    # المصادر نصياً فقط — لا تخمين
    url = _URL_RE.search(text or "")
    if url:
        out.artifacts["url"] = url.group(0).rstrip(".,،؛")
    path = _PATH_RE.search(text or "")
    if path and "url" not in out.artifacts:
        out.artifacts["url"] = path.group(1)
    return out


def _contains_phrase(stoks: List[str], phrase: List[str]) -> bool:
    stripped = [_strip_clitics(p) for p in phrase]
    for i in range(len(stoks) - len(stripped) + 1):
        if stoks[i:i + len(stripped)] == stripped:
            return True
    return False


def _term_index(stoks: List[str], term: str) -> Optional[int]:
    """موضع أول ظهور للمصطلح (رمزاً أو عبارة) في الرموز المجردة — أو None."""
    phrase = [_strip_clitics(p) for p in term.split()]
    if len(phrase) == 1:
        return stoks.index(phrase[0]) if phrase[0] in stoks else None
    for i in range(len(stoks) - len(phrase) + 1):
        if stoks[i:i + len(phrase)] == phrase:
            return i
    return None


def ranked_candidates(interpretation: IntentInterpretation,
                      registered_names: List[str]
                      ) -> Tuple[List[str], List[str]]:
    """المرشحون الملبّون (بترتيب الإيفاء المعلن) والمفاهيم بلا مُوفٍ.

    المرشح يجب أن يحقق **كل** المفاهيم المطلوبة (تقاطع لا اتحاد).
    الترتيب: قدرة مخصصة (مخرجها كله المفهوم) رتبتها 0، وعملية (المفهوم
    حقل بين حقول) رتبتها 1 — الأدنى أولاً. غير المسجل لا يُقترح."""
    if not interpretation.required_concepts:
        return [], []
    eligible: Optional[set] = None
    rank: Dict[str, int] = {}
    registration_index = {name: i for i, name in enumerate(registered_names)}
    for concept in interpretation.required_concepts:
        table = FULFILLMENT.get(concept, {})
        fulfillers = {cap for cap in table if cap in registered_names}
        if not fulfillers:
            return [], [concept]
        eligible = fulfillers if eligible is None else eligible & fulfillers
    for cap in eligible or set():
        rank[cap] = _rank_of(cap, interpretation)
    # الترتيب بفهرس التسجيل الفعلي (ترتيب السجل) لا أبجدياً — فقاعدة كسر
    # تعادل السياسة (stable-registration-order) تحترم ترتيب التسجيل الحقيقي
    ordered = sorted(rank, key=lambda c: (rank[c], registration_index[c]))
    return ordered, []


def build_mission(interpretation: IntentInterpretation,
                  registered_names: List[str]) -> Tuple[Optional[Dict[str, Any]],
                                                          Optional[str]]:
    """نية → مواصفة مهمة أو خطأ مسمّى (لا تنفيذ عند الغموض/الغياب)."""
    if interpretation.verbal_negation:
        return None, ("نفي فعلي (لا/ليس) نطاقه الجملة — لا آلية محدودة تحسم "
                      "ما نُفي بالضبط، فالطلب لا يُنفَّذ (غموض مسمّى: "
                      "intent-interpretation). المنفيات قيود تُعرض للمعتمِد لا "
                      "متطلبات تُحذف صامتة.")
    if interpretation.interrogative:
        return None, ("طلب استفهامي — سؤال لا أمر تنفيذ؛ يُوجَّه للبحث لا "
                      "للتنفيذ (فجوة مسماة: intent-interpretation)")
    if not interpretation.required_concepts:
        return None, ("لا مفاهيم مطلوبة مفهومة من الطلب — المعجم المعلن لم "
                      "يطابق شيئاً (فجوة مسماة: intent-interpretation)")
    candidates, unfulfilled = ranked_candidates(interpretation, registered_names)
    if unfulfilled:
        return None, ("لا قدرة مسجلة يحمل مخرجها المفهوم المطلوب: "
                      + ", ".join(unfulfilled)
                      + " (فجوة مسماة: intent-interpretation)")
    if not candidates:
        return None, ("لا قدرة مسجلة تحقق المفاهيم المطلوبة معاً: "
                      + ", ".join(interpretation.required_concepts)
                      + " (فجوة مسماة: intent-interpretation)")
    best_rank = _rank_of(candidates[0], interpretation)
    top = [c for c in candidates if _rank_of(c, interpretation) == best_rank]
    if len(top) > 1:
        return None, ("تعادل مرشحين بلا مميز من الطلب — لا اختيار بلا تعليل "
                      "في Instant (فجوة مسماة: intent-interpretation). المرشحون: "
                      + ", ".join(sorted(top))
                      + ". ميّز بالطلب (مثلاً «بصمة DNA») أو استخدم نمط "
                        "engine للمقارنة المعللة.")
    winner = top[0]
    if winner in NEEDS_REPOSITORY_SOURCE and "url" not in interpretation.artifacts:
        return None, ("المدخل المطلوب غائب: " + winner + " يحتاج مصدر مستودع "
                      "(رابط أو مسار) ولم يُذكر في الطلب (فجوة مسماة: "
                      "intent-interpretation)")
    parameters: Dict[str, Any] = dict(interpretation.artifacts)  # المستخرج فقط
    mission = {
        "name": "نية: " + " + ".join(sorted(interpretation.required_concepts)),
        "description": "مهمة مبنية من طلب طبيعي (مفسر النية المعلن)",
        "capability": winner,
        "parameters": parameters,
    }
    return mission, None


def _rank_of(cap: str, interpretation: IntentInterpretation) -> int:
    """أعلى (أسوأ) رتبة إيفاء للقدرة عبر المفاهيم المطلوبة."""
    worst = 0
    for concept in interpretation.required_concepts:
        entry = FULFILLMENT.get(concept, {}).get(cap)
        if entry:
            rank = 0 if entry[1] else 1
            worst = max(worst, rank)
    return worst
