# `templates/v1.5.9/`: The `agy` v1.5.9 CLI System Prompt

All 16 embedded `.tmpl` files in [`stock/system_prompts/`](./stock/system_prompts/) are identical to `v1.5.8`, so [`system_prompts/`](./system_prompts/) and [`prompt_overrides.json`](./prompt_overrides.json) carry forward from [`v1.5.8`](../v1.5.8/README.md).

What changed in `v1.5.9` ([`stock/PROMPT.md`](./stock/PROMPT.md)):
- Added the built-in `run-workflow` skill and the `run_workflow` tool schema (`1,835` chars).
- Loaded user-installed skills from `~/.gemini/config/skills/` dynamically into `<skills>` (redacted in `stock/PROMPT.md`).
- Dropped lazy MCP wrapper tools from the default no-MCP capture (`call_mcp_tool`, `list_resources`, `read_resource`), reducing the default tool count from 16 to 14.

## Editing

1. Edit a file in `system_prompts/` while preserving every Go `text/template` `{{ }}` action and staying within the original byte slot (`patch_agy.py` enforces slot limits).
2. Document the change in [`prompt_overrides.json`](./prompt_overrides.json) with a `reason`.
3. Re-apply and verify the rendered prompt:
   ```sh
   python3 ~/.gemini/agy-patch/patch_agy.py --apply
   python3 ~/.gemini/agy-patch/tools/capture_prompt.py
   ```
