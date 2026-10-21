#!/usr/bin/env python3
"""Write ``agos/agos-kernel/registry/manifest.json`` from a fresh kernel boot (R-Q-009).

    .venv/bin/python tools/audit/registry_manifest.py          # write
    .venv/bin/python tools/audit/registry_manifest.py --check  # exit 1 if stale
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KERNEL = REPO / "agos" / "agos-kernel"
TARGET = KERNEL / "registry" / "manifest.json"

PROBE = """
import json, agos_runtime
from registry import build_manifest
k = agos_runtime.boot().require_ready()
print(json.dumps(build_manifest(k.capability_registry, k.provider_registry, k.result.kernel_version)))
"""


def generate() -> str:
    out = subprocess.run([sys.executable, "-c", PROBE], cwd=KERNEL, capture_output=True,
                         text=True, timeout=120, check=True).stdout.strip().splitlines()[-1]
    return json.dumps(json.loads(out), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    fresh = generate()
    if "--check" in sys.argv:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != fresh:
            print(f"stale: {TARGET.relative_to(REPO)} — run tools/audit/registry_manifest.py")
            return 1
        print("registry manifest up to date")
        return 0
    TARGET.write_text(fresh, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
