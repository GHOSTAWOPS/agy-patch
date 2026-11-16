# `agy-patch`

English | [中文](README.zh.md)

Fail-closed, version-adaptive binary patcher, prompt-cache keepalive wrapper, powerline statusline, and upgrade-rehearsal toolchain for Google Antigravity CLI (`agy`, `darwin/arm64`).

> **Why this exists:** Official `agy` updates replace a single closed-source Go Mach-O binary (`~/.local/bin/agy`) and silently drop customizations. `agy-patch` anchors patches to Go `pclntab` symbols and instruction shapes, verifies every stock site before writing, isolates upgrades through dry-run rehearsal, and cleanly separates binary patching, runtime wrappers, and system-prompt overrides.

---

## Features

- **Context Window & Checkpointer Unlock** (`patch_agy.py`): Enables `/model` `Tab` context selection (`256K` / `512K` / `900K`) on Gemini 4 Argon, Carbon, and Hydrogen, removes >256K checkpoint and 64K `USER_INPUT` step clamps, and fixes statusline token accounting + 15s idle refresh.
- **TUI & CoT Readability**: Full multi-line `∴ Thought...` rendering (live one-liner under `medium` verbosity, full streaming block under `high`), native terminal `Faint` + `Italic` typography, semantic ANSI `"terminal"` palette alignment, adaptive Dark/Light full-width user prompt bar with live DEC 2031 theme switching, and the breathing Gemini star pending line.
- **System Prompt Trimming** (`templates/v<ver>/`): Byte-verified overrides for embedded `system_prompts/*.tmpl` slots with explicit per-file rationale in `prompt_overrides.json`.
- **Prompt Cache Keepalive Relay** (`runtime/agy-wrapper.sh` + `runtime/cache_relay.py`): Disables silent background auto-updates (`AGY_CLI_DISABLE_AUTO_UPDATE=true`) and keeps the 5-minute implicit prompt cache warm during idle stretches for interactive and `acp` sessions (`AGY_CACHE_RELAY=off` disables it).
- **Pastel Powerline Statusline** (`runtime/statusline.sh`): Single-pass `jq` telemetry bar showing context usage, tokens, step latency/TPS, quota, and cache TTL keepalive state (`↻`, `↻n`, `✗`).
- **Fail-Closed Upgrade Rehearsal** (`tools/probe_agy.py`): Downloads and SHA-512 verifies new releases in a temp workspace, resolves all patch sites, verifies instruction shapes (`site_shapes.json`), and probes wire payloads & PTY TUI screens before touching the installed binary.
- **Optional ACP MCP Hub** (`integrations/consult_gemini/`): Zero-dependency MCP stdio server + singleton Unix-socket Hub exposing read-only `consult_gemini` over persistent `agy acp` with SQLite `gen_metadata` telemetry.

---

## Requirements & Support Matrix

- **Platform**: macOS on Apple Silicon (`darwin/arm64`)
- **Dependencies**: Python `>= 3.12`, `jq`, Xcode Command Line Tools (`codesign`)
- **Supported `agy` releases**: `v1.5.3`, `v1.5.5`, `v1.5.6`, `v1.5.7`, `v1.5.8`, `v1.5.9`

---

## Quick Start (For Humans & Deploying Agents)

Paths are standardized around `~/.gemini/agy-patch`, `~/.local/bin/agy`, and `~/.gemini/bin/agy`.

### 1. Clone & Preview (`--dry-run`)

```sh
git clone https://github.com/wscffaa/agy-patch.git ~/.gemini/agy-patch
python3 ~/.gemini/agy-patch/scripts/install.py --dry-run
```

### 2. Install (Idempotent)

```sh
python3 ~/.gemini/agy-patch/scripts/install.py --set-window 512K
```

What `install.py` does:
1. Verifies OS/arch, Python `>= 3.12`, `codesign`, `jq`, and that `~/.local/bin/agy --version` has a matching `templates/v<ver>/` directory.
2. Backs up the clean binary to `~/.local/bin/agy.v<ver>.orig`, patches & ad-hoc signs `~/.local/bin/agy`.
3. Syncs [`runtime/agy-wrapper.sh`](runtime/agy-wrapper.sh) to `~/.gemini/bin/agy` and [`runtime/statusline.sh`](runtime/statusline.sh) to `~/.gemini/antigravity-cli/statusline.sh`.
4. Merges `statusLine` and `contextWindow` into `~/.gemini/antigravity-cli/settings.json` without overwriting existing settings.
5. Adds a managed `# >>> agy-patch >>>` block to `~/.zshrc` (`AGY_CLI_DISABLE_AUTO_UPDATE=true` + `alias agy="$HOME/.gemini/bin/agy"`). Pass `--skip-shell` to manage `~/.zshrc` yourself.

### 3. Verify

Open a new shell (or run `source ~/.zshrc`) and verify:

```sh
type agy
agy --version
python3 ~/.gemini/agy-patch/patch_agy.py --status -v
```

`type agy` should point to `~/.gemini/bin/agy`, and `patch_agy.py --status -v` should report `patched` for `~/.local/bin/agy` and `wrapper` for `~/.gemini/bin/agy`.

### Uninstall / Rollback

```sh
python3 ~/.gemini/agy-patch/scripts/install.py --uninstall
```

This restores `~/.local/bin/agy` from its `.orig` backup, removes the installed wrapper and statusline copy, cleans the managed `statusLine` entry, and strips the `# >>> agy-patch >>>` block from `~/.zshrc`.

---

## Safe Upgrade Workflow

Auto-update is disabled because background updates silently overwrite the patched binary (`updater.triggerUpdateShared` checks for the exact string `true`). Always rehearse an upstream release on isolated copies before upgrading:

```sh
# 1. Check whether a newer upstream release exists (read-only)
python3 -I ~/.gemini/agy-patch/tools/check_agy_update.py

# 2. Download, verify SHA-512, scaffold templates, check stock shapes, and probe wire/TUI on copies
python3 ~/.gemini/agy-patch/tools/probe_agy.py rehearse

# 3. Once rehearse reports ok (and you have reviewed any READ items):
env -u AGY_CLI_DISABLE_AUTO_UPDATE agy update
python3 ~/.gemini/agy-patch/patch_agy.py --apply
python3 ~/.gemini/agy-patch/patch_agy.py --status -v
```

If any anchor or stock shape fails, read [`docs/references/context-window-patch.md` §5](docs/references/context-window-patch.md#5-authoring-pitfalls) and [`CONTRIBUTING.md`](CONTRIBUTING.md) before changing a site.

---

## Repository Layout

| Path | Purpose |
| :--- | :--- |
| [`patch_agy.py`](patch_agy.py) | Primary version-adaptive ARM64 binary & template patcher (`--apply`, `--revert`, `--status`, `--accept-shapes`) |
| [`site_shapes.json`](site_shapes.json) | Masked stock instruction shapes for every reviewed site (fail-closed guard against shifted offsets) |
| [`runtime/`](runtime/agy-wrapper.sh) | Runtime wrapper (`agy-wrapper.sh`), cache keepalive relay (`cache_relay.py`), powerline bar (`statusline.sh`), optional `agy-gateway.env.example` |
| [`tools/`](tools/probe_agy.py) | Upgrade rehearsal (`probe_agy.py`), release checker (`check_agy_update.py`), Mach-O inspector (`inspect_agy.py`), prompt capture & scrubbing (`capture_prompt.py`, `prompt_templates.py`) |
| [`scripts/`](scripts/install.py) | Idempotent installer/uninstaller (`install.py`) and repo sustainability gate (`check_repo.py`) |
| [`templates/`](templates/v1.5.9/README.md) | Per-release (`v1.5.3`–`v1.5.9`) stock templates, captured `PROMPT.md`/`tools.json`, desired overrides, and `prompt_overrides.json` |
| [`integrations/`](integrations/consult_gemini_mcp.py) | Optional `consult_gemini` MCP stdio server + ACP Unix-socket Hub (`consult_gemini/`) |
| [`docs/`](docs/architecture.md) | Architecture overview, reverse-engineering references (`docs/references/`), and forensic diagnostics (`docs/diagnostics/`) |
| [`tests/`](tests/test_repo_invariants.py) | Offline unit & repo-invariant test suite (`python3 -m unittest discover -s tests -v`) |

---

## Checks & CI

Run the sustainability gate and test suite locally:

```sh
python3 ~/.gemini/agy-patch/scripts/check_repo.py
python3 -m unittest discover -s ~/.gemini/agy-patch/tests -v
```

GitHub Actions (`.github/workflows/ci.yml`) runs both on every push and pull request across Linux and macOS.

## License

[MIT](LICENSE)
