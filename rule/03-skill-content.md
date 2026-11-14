# 03. Skill content

1. Skills must be **agent-neutral**. Do not name one agent's tools, slash commands or config files in a skill body.
2. If a skill truly depends on an environment, declare it in the `compatibility` frontmatter field.
3. Frontmatter and description length are enforced by `tools/validate_skills.py`.
4. Derived content (for example from books) needs a `license` field and an entry in `THIRD_PARTY_NOTICES.md`.
5. Bundled scripts are cross-platform Python. Put tests in `scripts/test_*.py` with `fixtures/`.
