# Changelog

All notable milestones for `agy-patch` are recorded here.

## [0.1.0] - 2026-11-16

### Added
- Public repository structure (`runtime/`, `tools/`, `scripts/`, `integrations/`, `docs/`, `tests/`, `.github/workflows/ci.yml`).
- Idempotent installer and uninstaller (`scripts/install.py` with `--dry-run`, `--set-window`, `--uninstall`).
- Repository sustainability gate (`scripts/check_repo.py`) and offline unit test suite (`tests/`).
- `templates/v1.5.9/` support and `README.md` (`v1.5.9` adds `run-workflow` built-in skill and `run_workflow` tool).
- Automatic scrubbing in `tools/capture_prompt.py` for user rules, personal skills outside `<appDataDir>/builtin/skills/`, user MCP server listings, and `$HOME` paths.
- Bilingual root documentation (`README.md` and `README.zh.md`) and `docs/architecture.md`.

### Supported `agy` Releases
- `v1.5.3`, `v1.5.5`, `v1.5.6`, `v1.5.7`, `v1.5.8`, `v1.5.9` (`darwin/arm64`).
