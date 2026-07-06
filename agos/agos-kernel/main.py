#!/usr/bin/env python3
"""
AGOS Kernel - Main Entry Point

Runs a full, real Repository Analysis pipeline end-to-end:
clone -> read -> detect languages/frameworks -> generate DNA.

Usage:
    python main.py <github_url> [--branch <branch>]

Example:
    python main.py https://github.com/All-Hands-AI/OpenHands
"""
import json
import sys

from capabilities import RepositoryAnalysisCapability


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <github_url> [--branch <branch>]")
        sys.exit(1)

    url = sys.argv[1]
    branch = "main"

    if len(sys.argv) > 3 and sys.argv[2] == "--branch":
        branch = sys.argv[3]

    print("[AGOS] Starting Kernel v0.1.0")
    print(f"[AGOS] Mission: Analyze {url}")
    print("=" * 60)

    capability = RepositoryAnalysisCapability()

    print("\n[EXECUTING] Starting mission execution...\n")
    try:
        dna = capability.execute({"url": url, "branch": branch})
    except Exception as e:
        print(f"[FAILURE] Mission failed: {e}")
        sys.exit(1)

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
