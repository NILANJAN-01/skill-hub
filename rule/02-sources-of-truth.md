# 02. Sources of truth

| What | Where |
|---|---|
| The skill itself | `skills/<name>/SKILL.md` (+ `references/`, `scripts/`, `assets/`) |
| Plugin / category membership | `.claude-plugin/marketplace.json` (family bundles must also list their member skills) |
| Example prompts | `examples/prompts.json` (at least 2 per skill) |
| Folders each agent reads | `AGENTS` dict in `tools/install.py`. Change only from the vendor's official docs and update its `docs` link |
| Category display titles | `CATEGORY_TITLES` in `tools/build_catalog.py` |
| Skill format | `spec/agent-skills-spec.md`; start from `template/` |
