# skill-hub

[![Validate skills](https://github.com/NILANJAN-01/skill-hub/actions/workflows/validate.yml/badge.svg)](https://github.com/NILANJAN-01/skill-hub/actions/workflows/validate.yml)

**A centralized hub of Agent Skills that work in every major AI coding agent:** Claude Code, Google Antigravity, Devin, GitHub Copilot, Cursor, Windsurf, OpenAI Codex and Gemini CLI.

**New here? Follow the [step-by-step guide](GUIDE.md)**: install a skill into your agent in about 5 minutes.

Browse every skill in **[skills/README.md](skills/README.md)**. **[examples/PROMPTS.md](examples/PROMPTS.md)** shows what to say to your agent for each one.

A skill is a folder with a `SKILL.md` file in the open [Agent Skills](https://agentskills.io/specification) format. The YAML frontmatter (`name`, `description`) tells the agent *when* to use the skill. The Markdown body tells it *how*. Agents read only the descriptions up front and load the full skill when a task matches. Because the format is shared, each skill here is written **once** and installed into whichever agent you use.

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

## Install

### Option 1: the hub installer (detects your agents, asks first)

`tools/install.py` needs only Python 3.8+, with no clone and no Node. Run it with **no options**. It detects which AI agents and IDEs are installed, asks which of them to use (`a` for all, numbers for some, `n` for none), asks which skills and where, shows the exact plan, and installs only after you say yes. The [guide](GUIDE.md) walks through it step by step.

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py | python3 -

# Windows PowerShell
irm https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py -OutFile install.py
python install.py

# from a clone
python tools/install.py
```

The installer:
- **Reads the machine fresh on every run.** It looks for installed apps, commands on your PATH and the agents' config folders.
- **Writes to the fewest folders** that cover every agent you pick. For example, Copilot also reads Claude Code's and Codex's folders, so nothing gets installed twice.
- **Skips skills an agent can already see.** It asks before replacing a skill that differs from the hub, and offers to remove redundant identical copies. A repeat run reports *"Nothing to do"*.

To skip the questions (scripts, CI, dotfiles), pass options instead:

```bash
python install.py --detect                                        # which agents are installed
python install.py --list                                          # agents, plugins, skills
python install.py --agent detected --all --global --yes           # everything, every detected agent
python install.py --agent cursor --skill git-rebasing             # one skill, this project
python install.py --agent copilot,claude-code --plugin hub-tools --global
python install.py --agent codex --plugin git-skills --global --dry-run
python install.py --zip dist --plugin git-branching               # one .zip per skill, for upload UIs
```

`--force` replaces installed skills that differ from the hub, `--tidy` removes redundant copies, and `--each` copies into every agent's own folder instead of shared ones.

### Option 2: the `skills` CLI (Node)

The community [`skills`](https://skills.sh) CLI also installs from this repo into 40+ agents:

```bash
npx skills add NILANJAN-01/skill-hub --skill git-rebasing      # detects your agents
npx skills add NILANJAN-01/skill-hub --list
```

### Option 3: Claude Code plugin marketplace

```
/plugin marketplace add NILANJAN-01/skill-hub
/plugin install git-branching --marketplace NILANJAN-01/skill-hub
```

Plugins: `hub-tools`, `git-getting-started`, `git-branching`, `git-collaboration`, `git-power-tools`, `git-customization`, `git-internals`, `git-integrations`, `git-reference`, `git-skills` (all Git). On older Claude Code versions, add the marketplace first, then use `/plugin install <plugin>@skill-hub`.

### Option 4: copy a folder or upload a zip

Copy `skills/<name>/` into a folder from the table below. For web apps with an upload UI, such as Claude.ai (**Settings → Capabilities → Skills**) or the Devin web app, upload the zip that `install.py --zip` produces.

### Where each agent reads skills

<!-- agents:start -->
<!-- Generated from tools/install.py AGENTS by tools/build_catalog.py -->
| Agent | `--agent` | Project folder | User folder | Also reads |
|---|---|---|---|---|
| [Claude Code](https://code.claude.com/docs/en/skills) | `claude-code` | `.claude/skills` | `~/.claude/skills` | - |
| [Google Antigravity](https://antigravity.google/docs/skills) | `antigravity` | `.agents/skills` | `~/.gemini/config/skills` | `.agent/skills` |
| [Devin](https://docs.devin.ai/product-guides/skills) | `devin` | `.agents/skills` | `~/.config/devin/skills` | `.devin/skills`, `.github/skills`, `.claude/skills`, `.cursor/skills`, `.windsurf/skills`, `.codex/skills` |
| [GitHub Copilot (VS Code)](https://code.visualstudio.com/docs/agent-customization/agent-skills) | `copilot` | `.github/skills` | `~/.copilot/skills` | `.agents/skills`, `.claude/skills` |
| [Cursor](https://cursor.com/docs/skills) | `cursor` | `.cursor/skills` | `~/.cursor/skills` | `.claude/skills`, `.codex/skills` |
| [Windsurf (Devin Local)](https://docs.devin.ai/desktop/cascade/skills) | `windsurf` | `.devin/skills` | `~/.config/devin/skills` | `.windsurf/skills` |
| [OpenAI Codex](https://learn.chatgpt.com/docs/build-skills) | `codex` | `.agents/skills` | `~/.agents/skills` | - |
| [Gemini CLI](https://geminicli.com/docs/cli/skills/) | `gemini-cli` | `.gemini/skills` | `~/.gemini/skills` | `.agents/skills` |
| [Any Agent Skills tool (.agents)](https://agentskills.io) | `universal` | `.agents/skills` | `~/.agents/skills` | - |
<!-- agents:end -->

Commit project folders to share skills with your team. Install only the categories you need, because every installed skill adds its description to the agent's context. After installing, just describe the task. For example, *"rebase my feature branch onto main"* loads `git-rebasing`.

## Repository layout

```
skills/<name>/SKILL.md            one folder per skill, agent-neutral (+ optional references/, scripts/, assets/)
.claude-plugin/marketplace.json   groups skills into plugins/categories (used by Claude Code and install.py)
examples/prompts.json             example prompts for every skill (source)
examples/PROMPTS.md               generated, readable list of every example prompt
catalog.json, skills/README.md    generated index of every skill, plugins and agents
index.html, prompts.html          optional local browser for the catalog (python -m http.server)
template/SKILL.md                 starting point for a new skill
spec/agent-skills-spec.md         Agent Skills spec summary + hub conventions
tools/install.py                  multi-agent installer (source of truth for agent folders)
tools/build_catalog.py            regenerates catalog.json, skills/README.md, examples/PROMPTS.md, prompts.html, agent tables
tools/validate_skills.py          spec + hub + portability checks (CI)
GUIDE.md                          step-by-step guide for people using the skills
AGENTS.md                         instructions for AI agents working on this repo
```

## Add a skill to the hub

1. `cp -r template skills/<your-skill>` and fill in `SKILL.md`. Give it a specific `description` that says what the skill does and when to use it. Keep the body **agent-neutral**: no instructions that only one IDE understands.
2. Add `"./skills/<your-skill>"` to a plugin in `.claude-plugin/marketplace.json`, and add at least 2 example prompts for it to `examples/prompts.json`.
3. Run the tools:
   ```bash
   python tools/build_catalog.py      # regenerate generated files
   python tools/validate_skills.py    # spec + hub + portability checks
   ```
4. Open one pull request per skill, titled `Add <skill> skill` or `Update <skill> skill: <what changed>`. CI runs the same checks.

[CONTRIBUTING.md](CONTRIBUTING.md) has the full rules. Any agent working in this repo follows [AGENTS.md](AGENTS.md), and the [`contribute-skill`](skills/contribute-skill/SKILL.md) skill walks an agent through the whole process.

### Generate skills from a PDF

[`skills/skillforge`](skills/skillforge/SKILL.md) bundles `skillforge.py`, an offline generator that uses open-source NLP and needs no API key or LLM. It turns a technical PDF into focused playbooks, and it produced the Git skills here:

```bash
pip install -r skills/skillforge/scripts/requirements.txt
python skills/skillforge/scripts/skillforge.py book.pdf --plan-only     # review the plan
python skills/skillforge/scripts/skillforge.py book.pdf --topics "rebase, hooks, bisect"
```

## Browse the catalog locally (optional)

```bash
python -m http.server     # then open http://localhost:8000
```

## Disclaimer

Skills are provided as-is, for productivity and education. Generated skills are extracted from their sources and can contain noisy bullets. Review a skill and test it in your own environment before relying on it for critical work. Skills can include scripts, so read a skill before installing it from any source.

## Credits & licenses

- The `git-*` skills are derived from [*Pro Git*](https://git-scm.com/book) by Scott Chacon and Ben Straub, licensed under [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- Each skill declares its license in the `license` field of its frontmatter.
- The hub layout follows [anthropics/skills](https://github.com/anthropics/skills). Skill paths come from each vendor's documentation, linked in the table above.
