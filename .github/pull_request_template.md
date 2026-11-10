<!-- Title: "Add <name> skill" or "Update <name> skill: <what changed>". One skill per PR. -->

## What & why

## Checklist

- [ ] `SKILL.md` has `name` (= folder), a specific `description` (what + when), `license`, `metadata.title` and `metadata.category`
- [ ] The body is agent-neutral (no agent-specific tools or commands), or this is declared in `compatibility`
- [ ] Listed in a plugin in `.claude-plugin/marketplace.json`
- [ ] At least 2 prompts in `examples/prompts.json`
- [ ] Ran `python tools/build_catalog.py` and committed the generated files
- [ ] `python tools/validate_skills.py` shows 0 errors
- [ ] Tested in at least one agent (`python tools/install.py --agent <agent> --skill <name>`): it loads for a matching prompt and not for an unrelated one. Agent(s) tested:
