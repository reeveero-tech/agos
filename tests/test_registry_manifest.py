"""Versioned registry manifest (R-Q-009)."""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"
MANIFEST = KERNEL / "registry" / "manifest.json"


def test_committed_manifest_matches_a_fresh_boot():
    r = subprocess.run([sys.executable, str(REPO / "tools/audit/registry_manifest.py"), "--check"],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr


def test_manifest_is_versioned_and_consistent_with_runtime():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    code = ("import json, agos_runtime; k = agos_runtime.boot(); "
            "print(json.dumps([k.result.kernel_version, k.manifest()]))")
    out = subprocess.run([sys.executable, "-c", code], cwd=KERNEL, capture_output=True,
                         text=True, timeout=180, check=True).stdout.strip().splitlines()[-1]
    kernel_version, live = json.loads(out)
    assert data["schema"] == 1 and data["version"] == kernel_version
    assert data["capabilities"] == live["capabilities"] and data["providers"] == live["providers"]
    assert all(e["version"] for e in data["capabilities"] + data["providers"])
    # the manifest tells the truth about coverage: GenerateDNA has no provider yet (R-W3-003)
    provided = {s for p in data["providers"] for s in p["skills"]}
    assert "GenerateDNA" not in provided and {"CloneRepository", "ReadRepository"} <= provided
