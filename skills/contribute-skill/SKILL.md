---
name: contribute-skill
description: Add a new skill (or update an existing one) in the skill-hub repository so that it validates, appears in catalog.json and the generated skill lists, and installs into every supported AI coding agent (Claude Code, Antigravity, Devin, Copilot, Cursor, Windsurf, Codex, Gemini CLI). Use when the user wants to write, add, publish, register, contribute or rename a skill in skill-hub, create a new plugin bundle, or fix validation/catalog errors from tools/validate_skills.py or tools/build_catalog.py.
license: Complete terms in the repository README
compatibility: Works in any agent. Edits a skill-hub checkout, so it needs file-system and shell access with Python 3.8+. Mentions agent names only to explain where skills are installed.
metadata:
  title: "Contribute a skill to the hub"
  category: hub-tools
---

# Contribute a skill to skill-hub

Every skill in the hub lives in `skills/<name>/` and is registered in a plugin (category) in `.claude-plugin/marketplace.json`. Claude Code reads that file natively, and `tools/install.py` uses it to install categories into other agents. Two scripts keep the hub consistent:

- `tools/validate_skills.py` checks every skill against the Agent Skills spec and the hub rules.
- `tools/build_catalog.py` regenerates `catalog.json`, `skills/README.md`, `examples/PROMPTS.md`, `prompts.html`, and the agent tables in `README.md` and `GUIDE.md`. The `find-skills` skill and the installer read these.

## Procedure

1. **Pick a name**: lowercase letters, digits and hyphens, at most 64 characters, unique in `skills/`. Use a family prefix for a family of skills (e.g. `git-`, `docker-`).
2. **Create the folder** from the template:
   ```bash
   cp -r template skills/<name>
   ```
3. **Write the frontmatter** in `skills/<name>/SKILL.md`:
   ```yaml
   ---
   name: <name>                  # must equal the folder name
   description: <what it does>. Use when <triggers: tasks, keywords, commands, error messages>.
   license: <SPDX id or short terms>   # required for third-party-derived content
   metadata:
     title: "<Human readable title>"
     category: <plugin/category name, e.g. git-branching>
     source: "<origin, if derived from a document>"   # optional
     pages: "<page range>"                            # optional
   ---
   ```
   The `description` is the only thing an agent sees before it loads the skill. Make it specific (what plus when), at most 1024 characters, written in the third person, and include the words users actually type.
4. **Write the body.** Keep it actionable: when to use, when not to use, numbered procedures with exact commands, safety rules for destructive steps, and troubleshooting. Keep `SKILL.md` under about 500 lines. Move long material into `references/*.md`, and put helper code in `scripts/`. Link both with relative paths so that the agent loads them only when needed.
   **Keep it agent-neutral.** The same folder is installed into many different agents. Describe *what* to do ("run", "read", "ask the user") and don't name one agent's tools, slash commands or config files. Scripts must be cross-platform (Python standard library preferred). If a skill really needs a specific agent or environment, say so in the `compatibility` frontmatter field. Otherwise the validator warns about agent-specific wording.
5. **Register it** in `.claude-plugin/marketplace.json`. Add `"./skills/<name>"` to the `skills` array of the matching focused plugin, and to a bundle plugin (e.g. `git-skills`) if one exists for its family. To add a new plugin:
   ```json
   {
     "name": "<plugin-name>",
     "description": "<one sentence>",
     "source": "./",
     "strict": false,
     "category": "<category>",
     "skills": ["./skills/<name>"]
   }
   ```
   Add the plugin's display title to `CATEGORY_TITLES` in `tools/build_catalog.py`.
6. **Add example prompts** to `examples/prompts.json` (at least 2, ideally 3): `"<name>": ["realistic user request 1", "..."]`. Write them the way users actually ask. They appear in `examples/PROMPTS.md` and the local catalog browser.
7. **Rebuild and validate**:
   ```bash
   python tools/build_catalog.py
   python tools/validate_skills.py
   ```
   Fix every `ERROR`. Read each `WARN` and fix it where reasonable. CI runs both scripts with `--check` and fails if `catalog.json` is stale.
8. **Check the result.** The skill should appear in `skills/README.md` and `examples/PROMPTS.md`. For an optional visual check, run `python -m http.server` and open `http://localhost:8000/#/skill/<name>`.
9. **Open one pull request per skill**, titled `Add <name> skill` or `Update <name> skill: <what changed>`. Commit the skill folder, `marketplace.json`, `examples/prompts.json`, and all the generated files (`catalog.json`, `skills/README.md`, `examples/PROMPTS.md`, `prompts.html`, `README.md`, `GUIDE.md`) together.

## Common validation errors

| Error | Fix |
|---|---|
| `name 'X' does not match folder 'Y'` | Rename the folder or the `name` field so that they are equal |
| `name must be lowercase letters, digits and single hyphens` | No capitals, spaces, underscores, leading/trailing or double hyphens |
| `description is longer than 1024 characters` | Shorten it. Move detail into the body |
| `not listed in any plugin` | Add it to a plugin in `marketplace.json` (step 5) |
| `marketplace lists missing skill` | Fix the path or remove the entry |
| `agent-specific wording (...)` | Rewrite those lines neutrally, or add a `compatibility:` field explaining the requirement |
| `broken relative link` | Create the referenced file or fix the link path |
| `needs at least 2 example prompts` | Add prompts for the skill to `examples/prompts.json` |
| `catalog.json is out of date` | Run `python tools/build_catalog.py` and commit the result |
