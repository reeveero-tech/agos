#!/usr/bin/env python3
"""Count roadmap items per track and status from ROADMAP.md (used to update PROJECT_STATE.md)."""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROW = re.compile(r"^\|\s*(R-([A-Z0-9]+)-\d{3})\s*\|.*\|\s*(TODO|DOING|PARTIAL|DONE|BLOCKED)\s*\|\s*$")
text = (Path(__file__).resolve().parents[2] / "ROADMAP.md").read_text(encoding="utf-8")
per, total, ids = defaultdict(Counter), Counter(), []
for line in text.splitlines():
    m = ROW.match(line)
    if m:
        ids.append(m.group(1))
        per[m.group(2)][m.group(3)] += 1
        total[m.group(3)] += 1
dups = [i for i, c in Counter(ids).items() if c > 1]
print("| المسار | DONE | PARTIAL | DOING | TODO | BLOCKED |\n|---|---|---|---|---|---|")
for t in ["G", "F", "W1", "W2", "W3", "W4", "W5", "Q", "D", "REL"]:
    c = per[t]
    print(f"| {t} | {c['DONE']} | {c['PARTIAL']} | {c['DOING']} | {c['TODO']} | {c['BLOCKED']} |")
print(f"\nTOTAL items={len(ids)} " + " ".join(f"{k}={v}" for k, v in sorted(total.items())))
if dups:
    print("DUPLICATE IDS:", dups)
    sys.exit(1)
