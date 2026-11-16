# `templates/v1.5.3/`: The Whole `agy` v1.5.3 CLI System Prompt

The CLI system prompt, section by section, in the order the model receives it (`agy v1.5.3`). Google's originals are in [`stock/`](./stock/): the rendered prompt ([`PROMPT.md`](./stock/PROMPT.md)), tool schemas, and every template byte for byte. Template sections live in [`system_prompts/`](./system_prompts/) and are the desired state that `patch_agy.py --apply` writes into the binary. Go-generated sections are in [`go_generated.md`](./go_generated.md), read-only. `patch_agy.py` uses this directory only for a binary that reports `v1.5.3`.

| # | Section | Source | Status | Chars sent (stock → now) |
| ---: | :--- | :--- | :--- | ---: |
| 1 | `identity` | [`identity.tmpl`](./system_prompts/identity.tmpl) | Google's, unchanged | 453 |
| 2 | `artifacts` | [`artifacts.tmpl`](./system_prompts/artifacts.tmpl) | **Removed** (empty file) | 3,692 → 0 |
| 3 | `conversation_transcript` | [`conversation_transcript.tmpl`](./system_prompts/conversation_transcript.tmpl) | **Rewritten** | 1,915 → 429 |
| 4 | `guidelines` | [`guidelines.tmpl`](./system_prompts/guidelines.tmpl) | **Rewritten** | 1,227 → 209 |
| 5 | `communication_style` | [`communication_style.tmpl`](./system_prompts/communication_style.tmpl) | **Rewritten** | 478 → 123 |
| 6 | `slash_commands` | [`slash_commands.tmpl`](./system_prompts/slash_commands.tmpl) | **Removed** (empty file) | 1,492 → 0 |
| 7 | `messaging` | Go | read-only | 851 |
| 8 | `mcp_servers` | Go + your MCP config | read-only | 1,071 |
| 9 | `subagents` | Go + agent config | read-only | 2,042 |
| 10 | `skills` | [`skills.tmpl`](./system_prompts/skills.tmpl) + skill list | **Rewritten** (omits stock guides) | 1,977 → 0 |
| 11 | `user_rules` | Go + your `AGENTS.md` | read-only | 1,493 |
| 12 | `user_information` | Go + session | read-only | 428 |
| | **Total** | | | **17,499 → 7,400** |

`ephemeral_message`, `function_call`, `persistent_context`, `test_funcmap` and `helpers/async_termination_rule` are system prompt templates the CLI never renders; they are kept unchanged so the folder mirrors the binary.

## Editing

1. Edit a file in `system_prompts/`. Keep every `{{ }}` action: they are Go `text/template` code that `agy` runs each turn, and the text must fit the original slot (`patch_agy.py` reports the limit).
2. Add or update its `reason` in [`prompt_overrides.json`](./prompt_overrides.json).
3. `python3 ~/.gemini/agy-patch/patch_agy.py --apply`, then `python3 ~/.gemini/agy-patch/capture_prompt.py` to see the prompt the model now receives (`.cache/system-prompt/v<ver>/PROMPT.md`; diff it against `stock/PROMPT.md`).

An empty file removes its section; restoring Google's text from `stock/` restores it. Patching from the clean backup stops unless every template in the binary equals its `stock/` copy byte for byte, and unless every changed file has a `reason`.

After an `agy` upgrade there is no `templates/v<new>/`, so patching stops. To create it: `prompt_templates.py --dump templates/v<new>/stock --binary ~/.local/bin/agy.v<new>.orig` and `capture_prompt.py --binary ~/.local/bin/agy.v<new>.orig`, copy `system_prompts/` and `prompt_overrides.json` from this directory, `diff -r` the old and new `stock/`, and carry each upstream change into `system_prompts/`.
