# Architecture Overview

`agy-patch` is organized around four decoupled layers so that upstream `agy` binary updates never break runtime configuration silently.

## 1. Fail-Closed Binary Patcher (`patch_agy.py`, `site_shapes.json`, `templates/`)

- **Single source of truth**: Every `--apply` rebuilds `~/.local/bin/agy` from the clean backup `~/.local/bin/agy.v<ver>.orig`, applying all resolved ARM64 sites and `templates/v<ver>/system_prompts/` overrides, then ad-hoc re-signing with `codesign -f -s -`.
- **Version-adaptive resolution**: `patch_agy.py` parses the Mach-O `__lrodata_gopcln` Go symbol table and matches invariant instruction anchors instead of hardcoding offsets.
- **Shape guard (`site_shapes.json`)**: Before writing a single byte, `patch_agy.py` masks addresses/stack slots/struct fields at every resolved site and verifies the stock code matches a previously reviewed shape. Unreviewed shapes fail closed with instructions to inspect via `tools/probe_agy.py sites`.
- **Template slot parity (`tools/prompt_templates.py`)**: Refuses to patch if the binary's version has no `templates/v<ver>/` directory, if any stock template differs from `stock/`, or if a changed file in `system_prompts/` lacks a `reason` in `prompt_overrides.json`.

## 2. Runtime Layer (`runtime/`)

- **`runtime/agy-wrapper.sh` → `~/.gemini/bin/agy`**:
  - Exports `AGY_CLI_DISABLE_AUTO_UPDATE=true` so background auto-updates never overwrite the patched binary.
  - Passes `--hub` (VS Code extension) directly to `~/.local/bin/agy`.
  - Starts `runtime/cache_relay.py` for interactive and `acp` sessions and exports `CLOUD_CODE_URL` to keep the 5-minute implicit prompt cache warm during idle periods (`AGY_CACHE_RELAY=off` disables it).
- **`runtime/statusline.sh` → `~/.gemini/antigravity-cli/statusline.sh`**:
  - Single-pass `jq` telemetry renderer showing context percentage, token counts, step latency/TPS, quota, and cache TTL countdown/keepalive indicators (`↻`, `↻n`, `✗`).

## 3. Sustainable Upgrade & Inspection Toolchain (`tools/`)

- `tools/check_agy_update.py`: Reads the public release manifest and fetches + SHA-512 verifies newer binaries into a staging directory.
- `tools/probe_agy.py`: Runs `rehearse`, `wire`, `tui` (PTY snapshot diff), and `sites` against isolated temp directories and a loopback server — zero quota spent, zero live binary mutation.
- `tools/inspect_agy.py`: Fast Go `pclntab` symbol, `BL` call-graph, string literal, and `render.Styles` / `ColorPalette` inspector.
- `tools/capture_prompt.py`: Captures exact system prompt + tool schemas via loopback HTTP 500, scrubbing workspace paths, `$HOME`, user rules, personal skills, and configured MCP servers before writing `PROMPT.md`.

## 4. Optional Integrations (`integrations/`)

- `integrations/consult_gemini/` + `integrations/consult_gemini_mcp.py`: Zero-dependency MCP stdio server + singleton Unix-socket Hub (`~/.gemini/antigravity-acp/hub.sock`) exposing read-only `consult_gemini` over persistent `agy acp` with SQLite `gen_metadata` usage telemetry.

## Further Reading

- [Context window, CoT, palette & authoring pitfalls](references/context-window-patch.md)
- [TUI styles & color palette map](references/tui-styles-and-palette.md)
- [Pending line, breathing star & thought streaming](references/pending-line.md)
- [System prompt assembly & override surfaces](references/system-prompt.md)
- [Subagents & model catalog](references/subagents-and-models.md)
- [Hub & VS Code extension routing](references/hub-and-vscode-extension.md)
- [Forensic diagnostics](diagnostics/2026-11-04-400-investigation.md)
