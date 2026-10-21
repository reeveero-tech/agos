#!/usr/bin/env python3
"""Generate docs/architecture/MODULE_REGISTER.md — one row per package with its
architectural layer, concept group, roadmap items and computed liveness level.

Liveness levels (ADR-0003):
    L0  dead       — at least one file fails to import
    L1  importable — every file imports
    L2  connected  — reachable from a runtime entry point (boot path / CLI)
    L3  tested     — exercised by at least one test module
    L4  real       — L2 + L3 and zero stub functions

Run after tools/audit/inventory.py.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from module_map import DOC_PACKAGES, LAYERS, MODULES  # noqa: E402

INV = REPO / "docs" / "audit" / "inventory.json"
OUT = REPO / "docs" / "architecture" / "MODULE_REGISTER.md"

# Runtime entry points. Extended by R-W3-001 / R-W4-006 as the boot path grows.
ENTRY_POINTS = {"K:main", "K:bootstrapper", "S:agos_runtime", "K:agos_runtime"}


def package_key(path: str) -> str:
    parts = Path(path).relative_to("agos").parts
    if parts[0] == "agos-kernel":
        return "agos-kernel/" + parts[1] if len(parts) > 2 else "agos-kernel"
    return parts[0]


def is_test(i: dict) -> bool:
    name = i["module"].split(".")[-1]
    return name.startswith("test_") or ".tests" in i["module"] or i["module"].startswith("tests")


def main() -> int:
    data = json.loads(INV.read_text())
    files = data["files"]
    by_id = {f["id"]: f for f in files}

    # reachability from entry points over the import graph
    reach, stack = set(), [e for e in ENTRY_POINTS if e in by_id]
    while stack:
        cur = stack.pop()
        if cur in reach:
            continue
        reach.add(cur)
        stack += [r for r in by_id[cur].get("resolved_imports", []) if r not in reach]

    pk = defaultdict(list)
    for f in files:
        pk[package_key(f["path"])].append(f)

    rows, missing, levels = [], [], defaultdict(int)
    for key in sorted(pk):
        fs = pk[key]
        src = [f for f in fs if not is_test(f)]
        imp_ok = all(f.get("import_status", "OK") in ("OK", "SKIP") for f in fs)
        connected = any(f["id"] in reach for f in src) if src else False
        tested = any(any(is_test(by_id[x]) for x in f["imported_by"] if x in by_id) for f in src) or \
            (key == "agos-kernel" and any(is_test(f) for f in fs))
        stubs = sum(f["stub_functions"] for f in fs)
        if not imp_ok:
            lvl = "L0"
        elif not connected:
            lvl = "L1"
        elif not tested:
            lvl = "L2"
        elif stubs:
            lvl = "L3"
        else:
            lvl = "L4"
        levels[lvl] += 1
        layer, concept, items = MODULES.get(key, ("?", "?", []))
        if key not in MODULES:
            missing.append(key)
        rows.append((layer, key, concept, len(fs), sum(f["lines"] for f in fs), stubs,
                     "yes" if imp_ok else "NO", "yes" if connected else "no", "yes" if tested else "no",
                     lvl, ", ".join(items)))

    md = ["# سجل الوحدات — AGOS Module Register", "",
          "> مُولَّد آلياً بواسطة `tools/audit/module_register.py` من `docs/audit/inventory.json`. لا تحرره يدوياً.",
          "> المستويات (ADR-0003): L0 ميت · L1 قابل للاستيراد · L2 متصل بمسار التشغيل · L3 مختبَر · L4 حقيقي (متصل + مختبَر + بلا دوال فارغة).",
          "> **هدف المشروع: كل وحدة تصل إلى L4.**", "",
          "## ملخص المستويات", ""]
    for lv in ("L0", "L1", "L2", "L3", "L4"):
        md.append(f"- **{lv}**: {levels[lv]} حزمة")
    md += ["", "## الطبقات", ""] + [f"- **{k}** — {v}" for k, v in LAYERS.items()]
    md += ["", "## حزم الكود", "",
           "| layer | package | concept | files | lines | stub fns | imports | connected | tested | level | roadmap items |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows):
        md.append("| " + " | ".join(str(x) if i != 1 else f"`{x}`" for i, x in enumerate(r)) + " |")
    md += ["", "## حزم الوثائق والمواصفات (L0)", "", "| package | concept | roadmap items |", "|---|---|---|"]
    for k, (_, concept, items) in sorted(DOC_PACKAGES.items()):
        md.append(f"| `{k}` | {concept} | {', '.join(items)} |")
    if missing:
        md += ["", "## حزم غير مسجلة في module_map.py (يجب إضافتها)", ""] + [f"- `{m}`" for m in missing]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(md) + "\n")
    print(json.dumps({"levels": levels, "unmapped": missing}, ensure_ascii=False))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
