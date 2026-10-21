#!/usr/bin/env python3
"""
AGOS Kernel - Main Entry Point

Runs a full, real Repository Analysis pipeline end-to-end:
clone -> read -> detect languages/frameworks -> generate DNA.

Boot path (R-W3-001): ``agos_runtime.boot()`` -> ``Bootstrapper`` -> discovery ->
registries -> contract validation -> ``MissionEngine`` -> ``ExecutionPipeline`` ->
``RepositoryAnalysis`` capability (resolved, not hard-wired).

Usage:
    python main.py <github_url> [--branch <branch>]

Example:
    python main.py https://github.com/All-Hands-AI/OpenHands
"""
import json
import sys

import agos_runtime
from capabilities import RepositoryAnalysisCapability  # noqa: F401 - public re-export kept (G2)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <github_url> [--branch <branch>]")
        sys.exit(1)

    url = sys.argv[1]
    branch = "main"

    if len(sys.argv) > 3 and sys.argv[2] == "--branch":
        branch = sys.argv[3]

    kernel = agos_runtime.boot()
    print(f"[AGOS] Starting Kernel v{kernel.result.kernel_version}")
    if not kernel.ready:
        print(kernel.boot_log, end="")
        print(f"[FAILURE] Kernel boot failed: {'; '.join(kernel.errors)}")
        sys.exit(1)
    print(f"[AGOS] Booted via Bootstrapper: {len(kernel.result.loaded_capabilities)} capabilities, "
          f"{len(kernel.result.loaded_providers)} providers ({kernel.result.duration_ms}ms)")
    print(f"[AGOS] Mission: Analyze {url}")
    print("=" * 60)

    print("\n[EXECUTING] Starting mission execution...\n")
    try:
        outcome = kernel.analyze(url, branch=branch)
    except Exception as e:
        print(f"[FAILURE] Mission failed: {e}")
        sys.exit(1)
    if outcome.state.value != "completed":
        print(f"[FAILURE] Mission failed: {outcome.error}")
        sys.exit(1)
    dna = outcome.result
    print(f"[AGOS] Mission {outcome.mission_id} completed via "
          f"{' -> '.join(e['step'] for e in outcome.events)}")

    print("\n" + "=" * 60)
    print("[RESULT]")
    print("[SUCCESS] Mission completed!")

    output_file = "RepositoryDNA.json"
    with open(output_file, "w") as f:
        json.dump(dna.to_dict(), f, indent=2, default=str)
    print(f"[OUTPUT] Saved to {output_file}")

    print("\n[DNA SUMMARY]")
    print(f"  Name: {dna.name}")
    print(f"  Owner: {dna.owner}")
    print(f"  Primary Language: {dna.primary_language}")
    print(f"  Languages: {', '.join(dna.languages)}")
    print(f"  Frameworks: {', '.join(dna.frameworks) if dna.frameworks else 'None detected'}")
    print(f"  Package Managers: {', '.join(dna.package_managers) if dna.package_managers else 'None detected'}")
    print(f"  Config Files: {len(dna.config_files)}")
    print(f"  Directories: {len(dna.directory_tree)}")

    print("\n" + "=" * 60)
    print("[AGOS] Kernel stopped")


if __name__ == "__main__":
    main()
