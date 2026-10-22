"""
R-W2-008 — تحميل الرسم المعرفي من التحليل وحفظه.

يمتلئ الرسم المعرفي (``KnowledgeGraph``) من نتيجة تحليل مستودع (DNA) ويُحفظ
إلى قرص، ثم تُجاب الاستعلامات على الرسم المحمَّل لا على كائنات مُعدّة يدوياً.

المصادر المدعومة (محولات صريحة لا تخمين ``getattr``):
- DNA النواة (``agos_kernel.contracts.RepositoryDNA``): يحمل ``framework_evidence``
  و``dependency_details`` و``language_stats`` ولا يحمل ``commit``/``total_files``.
- DNA‏ rie (``agos.rie.contracts.RepositoryDNA``): يحمل ``commit`` و``total_files``
  و``dependency_details`` و``language_stats`` ولا يحمل ``framework_evidence``.

كل غياب دليل يُسجَّل فجوة باسمها في ``FillReport.gaps`` — لا يُختلق دليل ولا
يُفترى مصدر (سياسات ADR-0002 والمادة 6: لا تنفيذ صامت).

هذه العُقد إسقاطات بنيوية لحقائق التحليل (مستودع/حزمة/إطار/ملف)، وليست كائنات
معرفة دستورية — لا تُنشئ هنا كائنات معرفة تتجاوز النموذج المعتمد والمادة 13
(اختصاص توحيد المعرفة R-W1-005).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agos_kernel.civilization.knowledge_graph.knowledge_graph import KnowledgeGraph
from agos_kernel.civilization.knowledge_graph.nodes.base import GraphNode, NodeType
from agos_kernel.civilization.knowledge_graph.relationships import (
    Relationship,
    RelationshipType,
    create_relationship,
)

__all__ = [
    "FillReport",
    "fill_graph_from_dna",
    "fill_and_save",
]


@dataclass
class FillReport:
    """نتيجة ملء الرسم من تحليل: ما أُضيف وما نقص باسمه."""

    graph: KnowledgeGraph
    source_kind: str = ""            # "kernel" | "rie"
    nodes_added: int = 0
    relationships_added: int = 0
    gaps: List[str] = field(default_factory=list)  # غياب أدلة مسمّى — لا يُخفى


def _dna_source_kind(dna: Any) -> str:
    """نوع الـDNA المدعوم — أو استثناء باسم الغياب (لا تخمين صامت)."""
    if hasattr(dna, "framework_evidence"):
        return "kernel"   # DNA النواة: يحمل أدلة الأطر
    if hasattr(dna, "commit"):
        return "rie"      # DNA‏ rie: يحمل الالتزام وعدد الملفات
    raise ValueError(
        "Unsupported DNA shape: expected the kernel RepositoryDNA "
        "(framework_evidence) or the rie RepositoryDNA (commit) — got "
        f"{type(dna).__name__}"
    )


def _repo_identity(dna: Any) -> str:
    """هوية المستودع: الرابط إن وُجد (الاسم وحده لا يعرّف — قد يشترك فيه مالكان)."""
    url = (getattr(dna, "url", "") or "").strip()
    return url or dna.name


def _rel_exists(graph: KnowledgeGraph, source: str, target: str,
                rel_type: RelationshipType) -> bool:
    """هل العلاقة (مصدر/هدف/نوع) موجودة؟ — الملء المتكرر لا يكرر العلاقات."""
    for rid in graph._rel_source_index.get(source, set()):
        rel = graph._relationships.get(rid)
        if rel and rel.target_id == target and rel.type == rel_type:
            return True
    return False


def _add_once(graph: KnowledgeGraph, node: GraphNode, result: "FillReport") -> str:
    """إضافة عقدة بمعرف حتمي — إعادة ملء نفس التحليل لا تضاعف العُقد.

    ``GraphNode`` يولّد uuid عشوائياً افتراضياً؛ المعرف الحتمي (بصمة النوع/المسار/
    المستودع) هو ما يجعل الملء متكرر الآمن والهوية ثابتة عبر الحفظ والتحميل.

    التصحيح 0028: الحزمة نفسها قد تُصرَّح في أكثر من ملف اعتماديات — الدليل
    المتكرر لا يُستبدل بل يُجمَّع: كل الأدلة والظهورات (manifest/scope/specifier)
    تبقى على العقدة، فلا يفوز آخر ملف على أوله (المادة 6: لا فقد صامت).
    """
    node.id = node.generate_id()
    existing = graph._nodes.get(node.id)
    if existing is not None:
        for ev in node.metadata.evidence:
            if ev not in existing.metadata.evidence:
                existing.metadata.evidence.append(ev)
        for key, value in node.metadata.properties.items():
            if key == "occurrences":
                kept = existing.metadata.properties.setdefault("occurrences", [])
                for occ in value:
                    if occ not in kept:  # إعادة الملء لا تكرر الظهور نفسه
                        kept.append(occ)
            else:
                existing.metadata.properties[key] = value
        return existing.id
    graph.add_node(node)
    result.nodes_added += 1
    return node.id


def _add_rel_once(graph: KnowledgeGraph, rel: Relationship,
                  result: "FillReport") -> None:
    """إضافة علاقة مرة واحدة لكل (مصدر/هدف/نوع) — والدليل المتكرر يُجمَّع لا يُستبدل."""
    for rid in graph._rel_source_index.get(rel.source_id, set()):
        existing = graph._relationships.get(rid)
        if existing and existing.target_id == rel.target_id and existing.type == rel.type:
            for ev in rel.metadata.evidence:
                if ev not in existing.metadata.evidence:
                    existing.metadata.evidence.append(ev)
            return
    graph.add_relationship(rel)
    result.relationships_added += 1


def _repo_node(dna: Any, kind: str, report: FillReport) -> GraphNode:
    """عقدة المستودع بأدلة موجودة فعلاً — الغائبة تُسجَّل فجوة لا تُفترى."""
    identity = _repo_identity(dna)
    node = GraphNode(
        type=NodeType.REPOSITORY,
        name=dna.name,
        path=identity,
        repository=dna.name,
    )
    node.metadata.properties["analysis_source"] = kind
    node.metadata.properties["url"] = getattr(dna, "url", "") or ""
    node.metadata.properties["primary_language"] = (
        getattr(dna, "primary_language", "") or "")
    if getattr(dna, "language_stats", None):
        node.metadata.properties["language_stats"] = dict(dna.language_stats)
    evidence: List[str] = []
    if kind == "rie":
        if getattr(dna, "commit", ""):
            evidence.append(f"commit:{dna.commit}")
        else:
            report.gaps.append("repository: commit absent in rie DNA")
        if getattr(dna, "total_files", None):
            evidence.append(f"total_files:{dna.total_files}")
        else:
            report.gaps.append("repository: total_files absent in rie DNA")
    else:  # kernel DNA — لا commit ولا total_files فيه؛ الدليل المتاح مسار اللقطة وزمنها
        if getattr(dna, "snapshot_path", ""):
            evidence.append(f"snapshot:{dna.snapshot_path}")
        else:
            report.gaps.append("repository: snapshot_path absent in kernel DNA")
        if getattr(dna, "generated_at", None):
            evidence.append(f"generated_at:{dna.generated_at.isoformat()}")
    if not evidence:
        report.gaps.append("repository: no provenance field carried by the DNA")
    node.metadata.evidence.extend(evidence)
    return node


def _dependency_nodes(dna: Any, identity: str,
                     report: FillReport) -> List[GraphNode]:
    """عُقد الحزم: الهوية بالنظام البيئي (اسم واحد قد يتكرر عبر الأنظمة).

    التصحيح 0028: الحزمة نفسها قد تُصرَّح في أكثر من ملف — كل ظهور يُحفظ
    (occurrences) فلا يستبدل آخر ملف أوله، والأدلة تُجمَّع في العقدة والعلاقة.
    مسار العقدة مُسبَّق بهوية المستودع الكاملة (رابطه) — مستودعان بنفس الاسم
    في رسم واحد لا يتصادمان (الاسم وحده لا يعرّف).
    """
    nodes: List[GraphNode] = []
    details = list(getattr(dna, "dependency_details", None) or [])
    if details:
        for d in details:
            name = str(d.get("name", "")).strip()
            ecosystem = str(d.get("ecosystem", "")).strip()
            if not name:
                report.gaps.append("dependency: detail entry without a name")
                continue
            node = GraphNode(
                type=NodeType.PACKAGE,
                name=f"{ecosystem}:{name}" if ecosystem else name,
                path=f"{identity}/{ecosystem}:{name}" if ecosystem
                     else f"{identity}/pkg:{name}",
                repository=dna.name,
            )
            manifest = str(d.get("manifest", "") or "")
            specifier = str(d.get("specifier", "") or "")
            node.metadata.properties.update({
                "ecosystem": ecosystem,
                "occurrences": [{
                    "manifest": manifest,
                    "scope": str(d.get("scope", "") or ""),
                    "specifier": specifier,
                }],
            })
            if manifest:
                node.metadata.evidence.append(f"manifest:{manifest}")
            else:
                report.gaps.append(f"dependency {name}: manifest absent in detail")
            if specifier:
                node.metadata.evidence.append(f"specifier:{specifier}")
            nodes.append(node)
        return nodes
    # لا تفاصيل: الأسماء المجردة تُمثَّل بلا دليل — والغياب مسمّى لا مُقنَّع
    # (التصحيح 0029: هوية الابن هنا أيضاً بهوية المستودع الكاملة — لا بالاسم المشترك)
    for name in list(getattr(dna, "dependencies", None) or []):
        report.gaps.append(
            f"dependency {name}: dependency_details empty — no manifest evidence")
        nodes.append(GraphNode(
            type=NodeType.PACKAGE,
            name=name,
            path=f"{identity}/pkg:{name}",
            repository=dna.name,
        ))
    return nodes


def _framework_nodes(dna: Any, kind: str, identity: str,
                     report: FillReport) -> List[GraphNode]:
    """عُقد الأطر: دليل النواة صريح؛ وrie لا يحمل أدلة الأطر فتُسجَّل الفجوة باسمها.

    التصحيح 0028: دليل النواة قد يكون **استبعاداً** (counted=False — إطار مذكور
    في ملف اعتماديات لكنه لا يُعَدّ جزءاً من المشروع، مثل اعتمادية تطوير).
    الاستبعاد يُوثَّق ولا يُنشأ له USES — إظهار المستبعد استعمالاً إيجابية كاذبة.

    التصحيح 0029: الإطار الواحد قد له أكثر من سجل دليل (تصريح تشغيلي + استبعاد
    في ملف آخر) — السجلات كلها تُجمَّع (occurrences) ولا يستبدل آخرها أوله،
    وقرار الاستعمال مشتق من السجلات (أي سجل counted=True ⇒ استعمال)، فلا
    يستبدل استبعادٌ لاحقٌ استعمالًا موثَقًا بالفعل.
    """
    nodes: List[GraphNode] = []
    if kind == "kernel":
        # سجلات الدليل كلها تُجمَّع لكل إطار قبل بناء العقدة
        by_framework: dict = {}
        for ev in list(getattr(dna, "framework_evidence", None) or []):
            framework = str(ev.get("framework", "")).strip()
            if not framework:
                report.gaps.append("framework: evidence entry without a framework name")
                continue
            by_framework.setdefault(framework, []).append({
                "dependency": str(ev.get("dependency", "") or ""),
                "ecosystem": str(ev.get("ecosystem", "") or ""),
                "scope": str(ev.get("scope", "") or ""),
                "manifest": str(ev.get("manifest", "") or ""),
                "counted": bool(ev.get("counted", False)),
            })
        for framework, records in by_framework.items():
            node = GraphNode(
                type=NodeType.COMPONENT,
                name=framework,
                path=f"{identity}/framework:{framework}",
                repository=dna.name,
            )
            node.metadata.properties.update({
                "occurrences": records,
                # مشتق من السجلات — أي سجل counted=True يكفي للاستعمال
                "counted": any(r["counted"] for r in records),
            })
            for r in records:
                if r["manifest"]:
                    node.metadata.evidence.append(f"manifest:{r['manifest']}")
                else:
                    report.gaps.append(
                        f"framework {framework}: manifest absent in evidence")
                if not r["counted"]:
                    node.metadata.evidence.append(
                        "excluded:not counted as part of the project")
            nodes.append(node)
        return nodes
    for framework in list(getattr(dna, "frameworks", None) or []):
        report.gaps.append(
            f"framework {framework}: framework_evidence not carried by rie DNA")
        nodes.append(GraphNode(
            type=NodeType.COMPONENT,
            name=framework,
            path=f"{identity}/framework:{framework}",
            repository=dna.name,
        ))
    return nodes


def _file_nodes(dna: Any, attr: str, role: str, identity: str,
                report: FillReport) -> List[GraphNode]:
    """عُقد الملفات (نقاط الدخول بوصفها ملفات لا نقاط API — ليست API مُثبتة).

    التصحيح 0028: المسار مُسبَّق بهوية المستودع — مستودعان بنفس الاسم في رسم
    واحد لا يتصادمان على ملف بنفس الاسم.
    """
    nodes: List[GraphNode] = []
    for path in list(getattr(dna, attr, None) or []):
        if not path:
            continue
        node = GraphNode(
            type=NodeType.FILE,
            name=str(path).rstrip("/").split("/")[-1] or str(path),
            path=f"{identity}/{path}",
            repository=dna.name,
        )
        node.metadata.properties["role"] = role
        node.metadata.properties["raw_path"] = str(path)
        node.metadata.evidence.append(f"{role}:{path}")
        nodes.append(node)
    if not nodes:
        report.gaps.append(f"{role}: none listed in the DNA")
    return nodes


def fill_graph_from_dna(dna: Any,
                        graph: Optional[KnowledgeGraph] = None) -> FillReport:
    """املأ الرسم المعرفي من DNA تحليل مستودع.

    الملء تشغيلي متكرر: نفس التحليل لا يضاعف العُقد أو العلاقات (معرفات العُقد
    حتمية، والعلاقة تُضاف مرة لكل مصدر/هدف/نوع).

    التصحيح 0028: (1) الدليل المستبعد (counted=False) لا يُنشأ له USES —
    الاستبعاد يُوثَّق ولا يُدّعى استعمال. (2) الفجوات المسمّاة تُخزَّن في
    عقدة المستودع (analysis_gaps) فتنجو من الحفظ/التحميل ولا تضيع بين
    الذاكرة والقرص (المادة 6: لا فقد صامت).
    """
    kind = _dna_source_kind(dna)
    identity = _repo_identity(dna)
    graph = graph if graph is not None else KnowledgeGraph(name=dna.name or "analysis")
    report = FillReport(graph=graph, source_kind=kind)

    repo = _repo_node(dna, kind, report)
    repo_id = _add_once(graph, repo, report)

    # العلاقات: المستودع يعتمد على الحزم ويستخدم الأطر ويحيل لملفات الدخول
    # ويحتوي ملفات الإعداد — والأدلة على العلاقة نفسها لا على الطرفين فقط.
    for dep in _dependency_nodes(dna, identity, report):
        dep_id = _add_once(graph, dep, report)
        rel = create_relationship(
            RelationshipType.DEPENDS_ON, repo_id, dep_id,
            source_name=repo.name, target_name=dep.name)
        manifest_ev = [e for e in dep.metadata.evidence if e.startswith("manifest:")]
        rel.metadata.evidence.extend(manifest_ev or ["dependency listed in the DNA"])
        _add_rel_once(graph, rel, report)

    for fw in _framework_nodes(dna, kind, identity, report):
        fw_id = _add_once(graph, fw, report)
        if fw.metadata.properties.get("counted") is False:
            # استبعاد مُوثّق — لا USES للمستبعد (التصحيح 0028)
            continue
        rel = create_relationship(
            RelationshipType.USES, repo_id, fw_id,
            source_name=repo.name, target_name=fw.name)
        rel.metadata.evidence.extend(fw.metadata.evidence or
                                     ["framework listed without evidence"])
        _add_rel_once(graph, rel, report)

    for entry in _file_nodes(dna, "entry_points", "entry_point", identity, report):
        entry_id = _add_once(graph, entry, report)
        rel = create_relationship(
            RelationshipType.REFERENCES, repo_id, entry_id,
            source_name=repo.name, target_name=entry.name)
        rel.metadata.evidence.append(
            f"entry_point:{entry.metadata.properties.get('raw_path', entry.path)}")
        _add_rel_once(graph, rel, report)

    for cfg in _file_nodes(dna, "config_files", "config_file", identity, report):
        cfg_id = _add_once(graph, cfg, report)
        rel = create_relationship(
            RelationshipType.CONTAINS, repo_id, cfg_id,
            source_name=repo.name, target_name=cfg.name)
        rel.metadata.evidence.append(
            f"config_file:{cfg.metadata.properties.get('raw_path', cfg.path)}")
        _add_rel_once(graph, rel, report)

    # الفجوات المسمّاة تنجو من الحفظ/التحميل (التصحيح 0028)
    stored_repo = graph._nodes.get(repo_id)
    if stored_repo is not None:
        stored_repo.metadata.properties["analysis_gaps"] = list(report.gaps)

    return report


def fill_and_save(dna: Any, path: str,
                  graph: Optional[KnowledgeGraph] = None) -> FillReport:
    """املأ الرسم من التحليل واحفظه — الحفظ جزء المسار لا خطوة خارجية يدوية."""
    report = fill_graph_from_dna(dna, graph)
    report.graph.save(path)
    return report
