# skill-hub

[![Validate skills](https://github.com/NILANJAN-01/skill-hub/actions/workflows/validate.yml/badge.svg)](https://github.com/NILANJAN-01/skill-hub/actions/workflows/validate.yml)

**A centralized hub of Agent Skills for Claude.** Browse them at **https://nilanjan-01.github.io/skill-hub/**.

Skills are folders of instructions, scripts and resources that Claude loads on demand to do specialized tasks in a repeatable way. Each skill is a folder with a `SKILL.md` file. The YAML frontmatter (`name`, `description`) tells the agent *when* to use the skill. The Markdown body tells it *how*. Claude reads only the descriptions up front and loads the full skill when a task matches.

For background on skills, see:

- [What are skills?](https://support.claude.com/en/articles/12512176-what-are-skills)
- [Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude)
- [How to create custom skills](https://support.claude.com/en/articles/12512198-creating-custom-skills)
- [Agent Skills specification](https://agentskills.io/specification)

## What's in the hub

| Category (plugin) | Skills | What it covers |
|---|---:|---|
| [`hub-tools`](skills/README.md#hub-tools-hub-tools) | 3 | Find and install skills, contribute new ones, and generate skills from PDFs (`skillforge`) |
| [`git-getting-started`](skills/README.md#git-getting-started-git-getting-started) | 11 | Install and configure Git, create repos, record changes, history, undo, tags, aliases |
| [`git-branching`](skills/README.md#git-branching--merging-git-branching) | 7 | Branches, merging, remote branches, rebasing, advanced merge conflicts, rerere |
| [`git-collaboration`](skills/README.md#git-remotes--collaboration-git-collaboration) | 14 | Remotes, protocols, hosting Git servers, distributed workflows, GitHub, credentials |
| [`git-power-tools`](skills/README.md#git-power-tools-git-power-tools) | 11 | Revision selection, interactive staging, stash, signing, rewriting history, reset, bisect, submodules |
| [`git-customization`](skills/README.md#git-customization--hooks-git-customization) | 5 | Config, attributes, hooks, enforced policies, environment variables |
| [`git-internals`](skills/README.md#git-internals-git-internals) | 7 | Plumbing, objects, refs, packfiles, refspecs, transfer protocols, data recovery |
| [`git-integrations`](skills/README.md#git-other-systems--apis-git-integrations) | 5 | Git with SVN/Mercurial/Perforce, migrating to Git, PowerShell, JGit, libgit2 |
| [`git-reference`](skills/README.md#git-full-reference-git-reference) | 1 | The full *Pro Git* book as one reference skill |
| `git-skills` (bundle) | 61 | Every `git-*` skill above |

See the full list in [`skills/README.md`](skills/README.md). The machine-readable index is [`catalog.json`](catalog.json).

## Repository layout

```
.claude-plugin/marketplace.json   Claude Code plugin marketplace: groups skills into installable plugins
skills/<name>/SKILL.md            one folder per skill (+ optional references/, scripts/, assets/)
catalog.json, skills/README.md    generated index of every skill (tools/build_catalog.py)
template/SKILL.md                 starting point for a new skill
spec/agent-skills-spec.md         the Agent Skills spec summary + hub conventions
tools/                            build_catalog.py, validate_skills.py (stdlib-only Python)
index.html                        the GitHub Pages site (reads catalog.json)
```

## Use the skills

### Claude Code

Register this repository as a plugin marketplace:

```
/plugin marketplace add NILANJAN-01/skill-hub
```

Then select **Browse and install plugins** → **skill-hub** → a plugin → **Install now**. You can also install plugins directly:

```
/plugin install hub-tools --marketplace NILANJAN-01/skill-hub
/plugin install git-getting-started --marketplace NILANJAN-01/skill-hub
/plugin install git-branching --marketplace NILANJAN-01/skill-hub
/plugin install git-collaboration --marketplace NILANJAN-01/skill-hub
/plugin install git-power-tools --marketplace NILANJAN-01/skill-hub
/plugin install git-customization --marketplace NILANJAN-01/skill-hub
/plugin install git-internals --marketplace NILANJAN-01/skill-hub
/plugin install git-integrations --marketplace NILANJAN-01/skill-hub
/plugin install git-reference --marketplace NILANJAN-01/skill-hub
/plugin install git-skills --marketplace NILANJAN-01/skill-hub
```

On older Claude Code versions, add the marketplace first, then use `/plugin install <plugin>@skill-hub`.

Install only the categories you need, because every installed skill adds its description to Claude's context. After installing, just describe the task, e.g. *"rebase my feature branch onto main"* loads `git-rebasing`.

To install **a single skill** without the plugin system, copy its folder:

```bash
git clone --depth 1 https://github.com/NILANJAN-01/skill-hub.git
cp -r skill-hub/skills/git-rebasing ~/.claude/skills/            # all projects
cp -r skill-hub/skills/git-rebasing <project>/.claude/skills/    # one project
```

### Claude.ai

Zip a skill folder and upload it under **Settings → Capabilities → Skills**. See [Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude#h_a4222fa77b).

### Claude API

Upload a skill folder as a custom skill. See the [Skills API guide](https://docs.claude.com/en/api/skills-guide#creating-a-skill).

## Add a skill to the hub

1. `cp -r template skills/<your-skill>` and fill in `SKILL.md`. Give it a specific `description` that says what the skill does and when to use it.
2. Add `"./skills/<your-skill>"` to a plugin in `.claude-plugin/marketplace.json`.
3. Run the tools:
   ```bash
   python tools/build_catalog.py      # regenerate catalog.json + skills/README.md
   python tools/validate_skills.py    # spec + hub checks
   ```
4. Open a pull request. CI runs the same checks.

[CONTRIBUTING.md](CONTRIBUTING.md) has the full rules. The [`contribute-skill`](skills/contribute-skill/SKILL.md) skill teaches Claude to do all of this for you.

### Generate skills from a PDF

[`skills/skillforge`](skills/skillforge/SKILL.md) bundles `skillforge.py`, an offline generator that uses open-source NLP and needs no API key or LLM. It turns a technical PDF into focused playbooks, and it produced the Git skills here:

```bash
pip install -r skills/skillforge/scripts/requirements.txt
python skills/skillforge/scripts/skillforge.py book.pdf --plan-only     # review the plan
python skills/skillforge/scripts/skillforge.py book.pdf --topics "rebase, hooks, bisect"
```

## Preview the website locally

```bash
python -m http.server     # then open http://localhost:8000
```

## Disclaimer

Skills are provided as-is, for productivity and education. Generated skills are extracted from their sources and can contain noisy bullets. Review a skill and test it in your own environment before relying on it for critical work.

## Credits & licenses

- The `git-*` skills are derived from [*Pro Git*](https://git-scm.com/book) by Scott Chacon and Ben Straub, licensed under [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- Each skill declares its license in the `license` field of its frontmatter.
- The hub layout follows [anthropics/skills](https://github.com/anthropics/skills), which is also worth browsing for more skills.
