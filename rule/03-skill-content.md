# 03. Skill content

1. Skills must be **agent-neutral**. Do not name one agent's tools, slash commands or config files in a skill body.
2. If a skill truly depends on an environment, declare it in the `compatibility` frontmatter field.
3. Frontmatter and description length are enforced by `tools/validate_skills.py`, with token budgets: a description of at most about 130 tokens (every session reads it) and a SKILL.md body of at most about 5,000 tokens (every use reads it). A skill must save more tokens than it costs, so long procedures, tables and examples go in `references/`.
4. Derived content (for example from books) needs a `license` field and an entry in `THIRD_PARTY_NOTICES.md`.
5. Bundled scripts are cross-platform Python. Put tests in `scripts/test_*.py` with `fixtures/`.
