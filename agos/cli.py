"""Console entry point ``agos-analyze`` (R-F-001).

Runs the kernel's current working pipeline (``agos/agos-kernel/main.py``: clone a git
repository and write ``RepositoryDNA.json``) from any directory once AGOS is installed.
The boot path through ``Bootstrapper`` replaces this in R-W3-001; this wrapper stays as
the stable command name.

    agos-analyze <git-url> [--branch main]
"""
from __future__ import annotations

import importlib
import sys


def main(argv: list[str] | None = None) -> int:
    import agos  # noqa: F401  - installs the namespace/kernel finders (R-F-005)

    kernel_main = importlib.import_module("agos.kernel.main")
    if argv is not None:
        sys.argv = [sys.argv[0], *argv]
    result = kernel_main.main()
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    sys.exit(main())
