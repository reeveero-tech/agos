# AGOS - Autonomous General Orchestration System

A Python-based autonomous engineering system that clones, analyzes, and generates a structured "DNA" profile (languages, frameworks, dependencies, config, docs, security posture) of any Git repository, built from a large capability/provider/skill component library.

## Run & Operate

- `cd agos/agos-kernel && python3 main.py <github_url> [--branch <branch>]` — run the real end-to-end Repository Analysis pipeline (clone → read → detect languages/frameworks → generate DNA JSON)
- `cd agos/agos-kernel && python3 test_integration.py` — integration smoke test (module imports, repo analysis pipeline, AutonomousCore mission lifecycle). Bound to the "AGOS Kernel" workflow.
- `cd agos/agos-kernel && python3 test_civilization.py` — tests the higher-level Civilization runtime (mission compilation, execution graphs, governance, trust)
- Other `test_*.py` files in `agos/agos-kernel/` are legacy per-phase test scripts from the original spec; most pass standalone (see Gotchas for the two known exceptions)
- Python deps are managed via `uv` (root `pyproject.toml` / `uv.lock` / `.pythonlibs`)

## Stack

- Python 3.12, pure standard library + `requests`, `pyyaml`, `psutil`, `pytest`, `memory_profiler`
- No database, no web server — this is a CLI/library system, not a web app artifact
- Component model: **Capabilities** (high-level pipelines) → **Skills** (atomic operations) → **Providers** (external system adapters: GitHub, GitLab, SSH, Docker, REST, etc.)

## Where things live

- `agos/agos-kernel/capabilities/` — Capability classes (pipelines like RepositoryAnalysis, SecurityScan, LicenseAnalysis, etc.). Core repo-analysis pipeline in `__init__.py`; the 7 capabilities added to close spec gaps live in `foundation_extra.py`.
- `agos/agos-kernel/providers/` — Provider classes (GitHub/GitLab/Bitbucket/SSH/Container/CLI/REST/GraphQL/MCP/Local Execution, etc.). Core `LocalRepositoryProvider` in `__init__.py`; the 9 network/execution providers added to close spec gaps live in `network.py`.
- `agos/agos-kernel/skills/{code,file,analysis,knowledge,execution,vcs}/operations.py` — Skill classes grouped by domain (atomic operations like ReadFile, ParseAST, AnalyzeDocker, GenerateDNA, PublishArtifact, etc.)
- `agos/agos-kernel/core/` — `AutonomousCore`, the mission lifecycle engine (think/validate/execute/complete)
- `agos/agos-kernel/civilization/` — higher-level runtime: mission planning, knowledge graph, governance, certification, marketplace
- `agos/agos-kernel/main.py` — CLI entry point, runs the real Repository Analysis pipeline end-to-end
- `attached_assets/مهام_1783261223687.txt` — the original 14,746-line Arabic/English spec this project was built from (60 capabilities, 40 providers, 100 skills, all now present)

## Architecture decisions

- This is a fresh copy of the public `reeveero-tech/All-hand` reference repo, rebuilt inside this Replit workspace (not a live edit of the GitHub repo). Git history was intentionally not carried over.
- The reference repo evolved through multiple inconsistent historical "phases": some legacy test files (and the original `main.py`) referenced a removed `AGOSKernel` class from an earlier phase. The current working entry points are `capabilities.RepositoryAnalysisCapability` (real pipeline) and `core.AutonomousCore` (mission lifecycle) — `main.py` and `test_integration.py` were rewritten to use these directly.
- Not registered as a Replit "artifact" (web/mobile/etc.) — it's a standalone Python CLI/library, run via a console workflow instead.

## Product

Given a Git repository URL, AGOS clones it, walks its file tree, detects languages/frameworks/package managers, and produces a `RepositoryDNA` JSON profile. The broader component library (capabilities/providers/skills) also supports security scanning, license/documentation/configuration/infrastructure analysis, and knowledge extraction — these currently return structured stub data pending real-implementation follow-up work.

## User preferences

- User wants a fully self-contained Replit copy of the AGOS project (not edits to the live GitHub repo), covering as much of the original task spec as possible.

## Gotchas

- Two legacy test files still reference the removed `AGOSKernel` API: `test_validation.py` (won't import) and `test_intelligence.py` (imports fine but its Query Engine section hangs). Both are historical-phase artifacts from before the `core.AutonomousCore` rewrite — treat any future kernel-level test failures referencing `AGOSKernel` as this same known issue, not a new regression.
- `agos-kernel/platform/` was renamed to `agos-kernel/platform_runtime/` because it shadowed Python's stdlib `platform` module and broke imports project-wide.
- Paths were originally hardcoded to `/workspace/All-hand`; they now point to `/home/runner/workspace/agos`.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details (applies to the `artifacts/` API server and mockup sandbox, unrelated to the `agos/` Python project)
