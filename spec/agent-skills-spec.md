# Agent Skills Spec

The authoritative specification is at <https://agentskills.io/specification>.

This page summarizes the parts that `tools/validate_skills.py` enforces, plus the extra conventions this hub adds.

## Skill folder

```
<skill-name>/
  SKILL.md          # required: YAML frontmatter + Markdown instructions
  references/       # optional: docs loaded on demand
  scripts/          # optional: executable helpers
  assets/           # optional: templates, images, data
```

## SKILL.md frontmatter

| Field | Required | Rules |
|---|---|---|
| `name` | yes | 1–64 chars, lowercase `a-z`, `0-9` and single hyphens, no leading or trailing hyphen, **equals the folder name** |
| `description` | yes | 1–1024 chars. Says what the skill does **and when to use it** |
| `license` | no | License name or a pointer to a bundled license file |
| `compatibility` | no | ≤500 chars. Environment requirements |
| `metadata` | no | Map of string keys to string values |
| `allowed-tools` | no | Space-delimited list of pre-approved tools (experimental) |

## Hub conventions (on top of the spec)

- **Agent-neutral bodies.** Skills are installed into Claude Code, Antigravity, Devin, Copilot, Cursor, Windsurf, Codex and Gemini CLI. Don't rely on one agent's tool names, slash commands or config files. Put real requirements in `compatibility`. The validator warns on agent-specific wording.
- **Portable frontmatter only.** Use the spec fields above. Some agents support extra fields (e.g. `argument-hint`, `disable-model-invocation`), but others ignore or reject them, so put hub data under `metadata:`.
- **Scripts** are cross-platform (Python standard library preferred) and documented in the body.

- `metadata.title`: human-readable title shown on the website.
- `metadata.category`: the focused plugin the skill belongs to (e.g. `git-branching`).
- `metadata.source` / `metadata.pages`: provenance for skills derived from a document.
- `license` is required when the content is derived from third-party material.
- Every skill must be listed in at least one plugin in `.claude-plugin/marketplace.json`.
- Relative links in `SKILL.md` must resolve inside the skill folder.
- Keep `SKILL.md` under about 500 lines and move long material into `references/` (progressive disclosure).
