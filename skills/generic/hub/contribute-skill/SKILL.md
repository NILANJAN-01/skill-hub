---
name: contribute-skill
description: "Add or update a skill in the skill-hub repository so that it validates, appears in the catalog and installs into every supported agent. Use when the user wants to write, add, publish, register or rename a skill in skill-hub, create a plugin bundle, or fix errors from validate_skills.py, build_catalog.py or hub.py check."
license: Complete terms in the repository README
compatibility: Works in any agent. Edits a skill-hub checkout, so it needs file-system and shell access with Python 3.8+. Mentions agent names only to explain where skills are installed.
metadata:
  title: "Contribute a skill to the hub"
  category: hub-tools
---

# Contribute a skill to skill-hub

Every skill in the hub lives in `skills/<area>/<group>/<name>/` (areas: `testing`, `development`, `design`, `generic`, `external-tools`; a group is a subfolder of an area, and you may create a new one) and is registered in a plugin (category) in `.claude-plugin/marketplace.json`, which `tools/install.py` and the plugin marketplace read. `tools/hub.py` does the mechanical parts, so spend the effort on the skill's content, not on the registry:

| Command | Does |
|---|---|
| `python tools/hub.py new-skill <area>/<group>/<name> --plugin <plugin>` | Copies `template/`, writes the frontmatter, adds the skill to the plugin in `marketplace.json` and to `examples/prompts.json` (and creates a new plugin with its display title when asked), then rebuilds the generated files |
| `python tools/hub.py check --changed` | Rebuilds the generated files, then runs the validator, the stale-file check and the affected tests in parallel. Prints only what failed, with the command to rerun it |

If the checkout has no `tools/hub.py` (it is older), follow [Without hub.py](#without-hubpy).

## Procedure

1. **Pick the place and name.** Lowercase letters, digits and hyphens, at most 64 characters, unique across the whole hub (skills install by name alone). Use a family prefix for a family of skills (`git-`, `docker-`). Pick the plugin: list them with `python -c "import json; [print(p['name']) for p in json.load(open('.claude-plugin/marketplace.json'))['plugins']]"`.
2. **Scaffold and register** in one command. Pass the real description and prompts if you know them. Otherwise `TODO` placeholders are written, and the validator rejects them until they are replaced:
   ```bash
   python tools/hub.py new-skill development/docker/docker-compose-basics --plugin docker-tools \
     --description "Write and debug docker compose files. Use when the user mentions compose.yaml, services, volumes or docker compose up errors." \
     --prompt "Write a compose file for a web app and Postgres." \
     --prompt "docker compose up says the port is already allocated."
   ```
   - A new plugin (category): add `--plugin-title "Docker: compose & images" --plugin-description "<one sentence>"`.
   - A family bundle (for example all `git-*` skills): add `--also-plugin git-skills`.
   - Optional: `--title "Display title"`, `--license <SPDX id or terms>` (default MIT), and `--dry-run` to see the plan first.
3. **Write the description** (if you left the placeholder). It is the only thing an agent sees before it loads the skill: what it does plus when to use it, in the words users type, in the third person, under about 300 characters (hard limit 1024).
4. **Write the body** of `SKILL.md`, replacing all of the template text. Include when to use, when not to use, numbered procedures with exact commands, safety rules for destructive steps, and troubleshooting. Keep it under about 500 lines. Put long material in `references/*.md` (delete `references/details.md` if unused), helper code in `scripts/` with tests in `scripts/test_*.py` and `fixtures/`, and link both with relative paths.
   **Keep it agent-neutral.** The same folder is installed into many different agents. Describe *what* to do ("run", "read", "ask the user"), and don't name one agent's tools, slash commands or config files. Scripts must be cross-platform (Python standard library preferred). If a skill really needs a specific agent or environment, say so in the `compatibility` frontmatter field.
   Derived content (from a book, docs or another project) needs a `license` field, `metadata.source`, and an entry in `THIRD_PARTY_NOTICES.md`.
5. **Example prompts** (if you left the placeholders): at least 2, ideally 3, in `examples/prompts.json`, written the way users actually ask.
6. **Check** and fix every failure it prints:
   ```bash
   python tools/hub.py check --changed
   ```
   It also prints validator warnings. Fix them where reasonable. Before a release, or when the change touches tooling, run `python tools/hub.py check` with no flags.
7. **Open one pull request per skill**, titled `Add <name> skill` or `Update <name> skill: <what changed>`. Commit the skill folder, `marketplace.json`, `examples/prompts.json` (plus `tools/build_catalog.py` for a new plugin) and every generated file the build changed (`catalog.json`, `skills/README.md`, `examples/PROMPTS.md`, `prompts.html`, `user-guide.html`, `README.md`, `GUIDE.md`).

**Updating or renaming a skill:** edit its files, then run `hub.py check --changed`. To move or rename one, `git mv` the folder, change `name:` if the name changed, update its path in `marketplace.json` and its key in `examples/prompts.json`, then check.

The generated files are rebuilt by `check`. If the repository's hooks are set up (`python tools/hub.py setup-hooks --yes`), they are also rebuilt after every edit, and the check runs before the agent finishes and before each commit. Never edit the generated files by hand.

## Without hub.py

1. `cp -r template skills/<area>/<group>/<name>`, then write the frontmatter: `name` (equal to the folder), `description`, `license`, and `metadata.title` and `metadata.category` (the plugin).
2. Add `"./skills/<area>/<group>/<name>"` to the plugin's `skills` array in `.claude-plugin/marketplace.json`. A new plugin needs an entry with `name`, `description`, `"source": "./"`, `"strict": false`, `category` and `skills`, plus a display title in `CATEGORY_TITLES` in `tools/build_catalog.py`.
3. Add at least 2 prompts to `examples/prompts.json`.
4. Run `python tools/build_catalog.py`, `python tools/validate_skills.py` and `python tools/build_catalog.py --check`, and the skill's tests.

## Common validation errors

| Error | Fix |
|---|---|
| `description is still the TODO placeholder` / `replace the TODO placeholder prompts` | Write the real description or prompts (steps 3 and 5) |
| `still contains template text` | Replace the template's example sections in the body (step 4) |
| `name 'X' does not match folder 'Y'` | Rename the folder or the `name` field so that they are equal |
| `name must be lowercase letters, digits and single hyphens` | No capitals, spaces, underscores, leading/trailing or double hyphens |
| `description is longer than 1024 characters` | Shorten it. Move detail into the body |
| `not listed in any plugin` | Add it to a plugin in `marketplace.json` (`hub.py new-skill` does this) |
| `marketplace lists missing skill` | Fix the path (after a move) or remove the entry |
| `agent-specific wording (...)` | Rewrite those lines neutrally, or add a `compatibility:` field explaining the requirement |
| `broken relative link` | Create the referenced file or fix the link path |
| `needs at least 2 example prompts` | Add prompts for the skill to `examples/prompts.json` |
| `generated files up to date` fails / `catalog.json is out of date` | Run `python tools/hub.py check` (it rebuilds) and commit the generated files |
| `new-skill: no plugin 'X'` | Use a suggested name, or create it with `--plugin-title` and `--plugin-description` |
