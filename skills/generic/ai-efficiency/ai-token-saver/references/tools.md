# Where each AI coding tool reads its ignore and instruction files

Names change between versions. Confirm in the vendor's current docs before relying on one.

| Tool | Always-loaded instructions | Exclude files from context/index |
|---|---|---|
| Claude Code | `CLAUDE.md`, `AGENTS.md` (via import) | permission deny rules in its settings |
| Cursor | `.cursorrules`, `.cursor/rules/` | `.cursorignore`, `.cursorindexingignore` |
| Windsurf | `.windsurfrules` | `.codeiumignore` |
| GitHub Copilot | `.github/copilot-instructions.md` | content exclusion in repo/org settings |
| Gemini CLI | `GEMINI.md` | `.geminiignore` |
| Aider | `CONVENTIONS.md` (if added) | `.aiderignore` |
| Cline / Continue | `.clinerules` / `.continue/rules` | `.clineignore` / `.continueignore` |
| Other / web chat | paste a short brief | paste only the relevant slice |

Most of them also respect `.gitignore` for indexing, so start there.

## Model-neutral cost facts

- Cost is roughly input tokens plus output tokens, and output tokens usually cost several times more.
- A chat resends the whole history each turn, so long sessions grow quadratically in cost.
- Many providers discount repeated identical prefixes (prompt caching). Keep the stable part (instructions, files) first and unchanged; put the changing question last.
- Larger "reasoning" or "thinking" modes spend extra output tokens. Use them for hard problems only.
- Smaller models are far cheaper and fine for renames, formatting, boilerplate, summaries and simple tests.
