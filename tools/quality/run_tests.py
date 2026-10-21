#!/usr/bin/env python3
"""AGOS test runner with a ratchet baseline.

* Runs the whole pytest suite (kernel tests + repository tests/).
* Compares failures against docs/quality/test_baseline.json:
    - a failure NOT in the baseline  -> regression -> exit 1
    - a baseline entry that now passes -> reported; update the baseline in the
      same commit (ratchet only moves forward).
* Writes docs/quality/last_run.json with the summary used by PROJECT_STATE.md.

Usage:  python tools/quality/run_tests.py [--update-baseline]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KERNEL = REPO / "agos" / "agos-kernel"
BASELINE = REPO / "docs" / "quality" / "test_baseline.json"
LAST = REPO / "docs" / "quality" / "last_run.json"


def run() -> dict:
    with tempfile.TemporaryDirectory() as td:
        xml = Path(td) / "junit.xml"
        targets = [str(KERNEL)]
        if (REPO / "tests").is_dir():
            targets.append(str(REPO / "tests"))
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
               "--continue-on-collection-errors", f"--junitxml={xml}", *targets]
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=1800)
        tail = proc.stdout.strip().splitlines()[-1:] if proc.stdout.strip() else []
        res = {"passed": 0, "failed": [], "errors": [], "skipped": 0, "summary": tail[0] if tail else ""}
        if not xml.exists():
            res["errors"].append("pytest produced no report: " + proc.stderr[-500:])
            return res
        for tc in ET.parse(xml).getroot().iter("testcase"):
            node = f"{tc.get('classname')}::{tc.get('name')}".replace(str(REPO), "<repo>")
            kinds = {c.tag for c in tc}
            if "failure" in kinds:
                res["failed"].append(node)
            elif "error" in kinds:
                res["errors"].append(node)
            elif "skipped" in kinds:
                res["skipped"] += 1
            else:
                res["passed"] += 1
        res["failed"].sort()
        res["errors"].sort()
        return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-baseline", action="store_true")
    a = ap.parse_args()
    res = run()
    bad = set(res["failed"]) | set(res["errors"])
    LAST.parent.mkdir(parents=True, exist_ok=True)
    LAST.write_text(json.dumps({"passed": res["passed"], "failed": len(res["failed"]), "errors": len(res["errors"]),
                                "skipped": res["skipped"], "pytest_summary": res["summary"]}, indent=1) + "\n")
    print(f"passed={res['passed']} failed={len(res['failed'])} errors={len(res['errors'])} skipped={res['skipped']}")

    data = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    # "revealed": failures that were hidden by a vacuous test (e.g. scanning a path that did
    # not exist) and became real once that test was fixed. Each entry must name its reason
    # and the roadmap item that will fix it. They are tracked, never silently accepted.
    revealed = {k: v for k, v in data.get("revealed", {}).items()}
    if a.update_baseline or not BASELINE.exists():
        revealed = {k: v for k, v in revealed.items() if k in bad}
        out = {"known_failures": sorted(bad - set(revealed))}
        if revealed:
            out["revealed"] = dict(sorted(revealed.items()))
        BASELINE.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
        print(f"baseline written: {len(out['known_failures'])} known + {len(revealed)} revealed failures")
        return 0

    known = set(data["known_failures"]) | set(revealed)
    new = sorted(bad - known)
    fixed = sorted(known - bad)
    for f in fixed:
        print(f"  FIXED (remove from baseline in this commit): {f}")
    if fixed:
        print("  -> run with --update-baseline to ratchet forward.")
    if new:
        print("\n✗ REGRESSIONS (not in baseline):")
        for n in new:
            print("  - " + n)
        return 1
    print("✓ no regressions against baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
