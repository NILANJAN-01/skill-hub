# Using skill-hub: step-by-step guide

This guide takes you from nothing to a working skill in your AI coding agent in about 5 minutes. It works for **Claude Code, Google Antigravity, Devin, GitHub Copilot (VS Code), Cursor, Windsurf, OpenAI Codex and Gemini CLI**.

> **What's a skill?** A skill is a folder with a `SKILL.md` playbook. Once it's installed, your agent reads the skill's short description. When your request matches it, the agent loads the full playbook and follows it. You don't call skills by name; you just ask for what you want.

---

## Step 1: Check you have Python

The installer needs only **Python 3.8 or newer**. Open a terminal and run:

| System | Command | You should see |
|---|---|---|
| macOS / Linux | `python3 --version` | `Python 3.x.x` |
| Windows (PowerShell) | `python --version` | `Python 3.x.x` |

No Python? Install it from https://www.python.org/downloads/. On Windows, tick **"Add python.exe to PATH"**.

*(Prefer Node? You can use `npx skills` instead. See [Other ways to install](#other-ways-to-install).)*

## Step 2: Find the skill you want

Pick whichever is easiest:

- **Website:** https://nilanjan-01.github.io/skill-hub/. Search or filter by category, then open a skill.
- **Example prompts:** https://nilanjan-01.github.io/skill-hub/prompts.html. This shows what you'd say for each skill.
- **List in the repo:** [`skills/README.md`](skills/README.md).

Note the skill's **name**, such as `git-rebasing`, or the **category** (plugin) it's in, such as `git-branching`. You can install one skill or a whole category.

| Category | What's in it |
|---|---|
| `hub-tools` | Find and install skills, contribute skills, turn PDFs into skills |
| `git-getting-started` | Install and configure Git, first repo, commits, history, undo, tags |
| `git-branching` | Branches, merging, rebasing, merge conflicts |
| `git-collaboration` | Remotes, Git servers, GitHub, pull requests, credentials |
| `git-power-tools` | Stash, interactive staging, rewriting history, reset, bisect, submodules |
| `git-customization` | Config, attributes, hooks, policies |
| `git-internals` | Objects, refs, packfiles, data recovery |
| `git-integrations` | SVN/Mercurial/Perforce, migration, PowerShell, JGit, libgit2 |
| `git-reference` | The whole *Pro Git* book as one reference skill |
| `git-skills` | All 61 Git skills |

> **Tip:** Install only what you need. Every installed skill adds its description to your agent's context.

## Step 3: Pick your agent ID

| You use… | Agent ID |
|---|---|
| Claude Code | `claude-code` |
| Google Antigravity | `antigravity` |
| Devin | `devin` |
| GitHub Copilot in VS Code | `copilot` |
| Cursor | `cursor` |
| Windsurf | `windsurf` |
| OpenAI Codex | `codex` |
| Gemini CLI | `gemini-cli` |
| Something else that supports Agent Skills | `universal` |

Using more than one? List them all with commas, for example `cursor,copilot`. The installer picks the fewest folders that cover them all, so no agent sees the same skill twice.

## Step 4: Decide where to install

| Choice | When to use it | How |
|---|---|---|
| **This project** (default) | The skill is for one codebase, and you want to share it with your team through git | Run the command from inside your project folder |
| **Just me, everywhere** | You want the skill in all your projects | Add `--global` |

## Step 5: Run the installer

Go to your project folder first (`cd path/to/your-project`), then run the command for your system. Replace `<agent>` and pick `--skill` or `--plugin`.

**macOS / Linux**

```bash
curl -fsSL https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py | python3 - --agent <agent> --skill git-rebasing
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py -OutFile install.py
python install.py --agent <agent> --skill git-rebasing
```

**Examples**

```bash
# Cursor, one skill, this project
... --agent cursor --skill git-rebasing

# Antigravity, a whole category, this project
... --agent antigravity --plugin git-branching

# Copilot + Claude Code together, several skills
... --agent copilot,claude-code --skill git-rebasing,git-hooks

# Codex, all Git skills, for your user (every project)
... --agent codex --plugin git-skills --global

# See every agent, category and skill without installing anything
... --list

# Preview what would be written without writing it
... --agent cursor --plugin git-branching --dry-run
```

(`...` stands for the `curl … | python3 -` or `python install.py` part above.)

You'll see output like this:

```
Cursor: /home/you/my-project/.cursor/skills
  install  git-rebasing  ->  /home/you/my-project/.cursor/skills/git-rebasing

Installed 1 skill folder(s). Restart or reload the agent, ...
```

## Step 6: Restart or reload your agent

Most agents scan for skills when a session starts:

- **IDEs** (Antigravity, Cursor, Windsurf, VS Code with Copilot): reload the window or open a new chat.
- **CLIs** (Claude Code, Codex, Gemini CLI, Devin CLI): start a new session.
- **Cloud Devin:** commit and push the `.agents/skills/` folder to your repository. Devin reads skills from the repo.

## Step 7: Use it by just asking

Describe your task normally. For example, after installing `git-rebasing`:

> *"My feature branch is behind main. Put my commits on top of the latest main without a merge commit."*

The agent matches your request to the skill and follows its steps. The [example prompts page](https://nilanjan-01.github.io/skill-hub/prompts.html) has 3 ready-made prompts for every skill.

**Want to force a specific skill?** Name it:

> *"Use the git-hooks skill: block commits whose message doesn't start with a ticket ID."*

## Step 8: Check that it worked

- **Ask your agent:** *"Which skills do you have available?"* The installed skill's name should appear.
- **Check the folder:** open the folder shown in Step 5's output. There should be `<skill-name>/SKILL.md` inside.
- **If the agent answered without using the skill:** that can happen for simple questions the agent already knows well. Name the skill explicitly (Step 7) when you want its exact procedure.

## Step 9: Share it with your team (optional)

Project installs live in a folder inside your repo, such as `.agents/skills/` or `.cursor/skills/`. Commit it:

```bash
git add .agents/skills .cursor/skills     # whichever folders were created
git commit -m "Add skill-hub skills"
git push
```

Everyone who clones the repo now gets the skills in their agent automatically.

## Step 10: Update or remove skills

- **Update to the latest version:** run the same install command again with `--force`. Without `--force`, existing skills are left untouched.
- **Remove a skill:** delete its folder, for example `.cursor/skills/git-rebasing/`, or the same name in your global folder.

---

## Other ways to install

### `skills` CLI (needs Node.js)

```bash
npx skills add NILANJAN-01/skill-hub --skill git-rebasing             # asks which agents
npx skills add NILANJAN-01/skill-hub --skill git-rebasing -a cursor   # a specific agent
```

### Claude Code plugin marketplace

Inside Claude Code:

```
/plugin marketplace add NILANJAN-01/skill-hub
/plugin install git-branching --marketplace NILANJAN-01/skill-hub
```

Get updates with `/plugin marketplace update skill-hub`.

### Web apps with an upload button (Claude.ai, Devin web app, …)

Create a zip per skill, then upload it in the app's skills settings (for Claude.ai: **Settings → Capabilities → Skills**):

```bash
python install.py --zip skill-zips --skill git-rebasing      # creates skill-zips/git-rebasing.zip
```

### Manually

Download or clone the repo and copy `skills/<name>/` into your agent's folder:

<!-- agents-simple:start -->
<!-- Generated from tools/install.py AGENTS by tools/build_catalog.py -->
| Agent | This project | Just me |
|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Google Antigravity | `.agents/skills/` | `~/.gemini/config/skills/` |
| Devin | `.agents/skills/` | `~/.config/devin/skills/` |
| GitHub Copilot (VS Code) | `.github/skills/` | `~/.copilot/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| Windsurf (Devin Local) | `.devin/skills/` | `~/.config/devin/skills/` |
| OpenAI Codex | `.agents/skills/` | `~/.agents/skills/` |
| Gemini CLI | `.gemini/skills/` | `~/.gemini/skills/` |
<!-- agents-simple:end -->

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python3: command not found` (macOS/Linux) | Install Python 3, or try `python` instead of `python3` |
| `python` opens the Microsoft Store (Windows) | Install Python from python.org with "Add to PATH" ticked, or use `py install.py ...` |
| On Windows, `curl ... \| python3 -` fails | Use the PowerShell commands from Step 5 (`irm ... -OutFile install.py`, then `python install.py ...`) |
| `skip ... (exists; use --force to replace)` | The skill is already installed. Add `--force` to update it |
| `Unknown skill` / `Unknown plugin` | Check the spelling with `--list` |
| `unknown agent` | Use one of the IDs from Step 3 |
| Download fails or times out | Check your internet or proxy, or clone the repo and run `python tools/install.py ...` from it |
| Agent doesn't see the skill | Restart or reload it (Step 6), check that you ran the command from the project root, and that the folder matches the agent (Step 8) |
| The same skill appears twice | It's in two folders your agent reads. Delete one copy. The installer avoids this when you list all your agents in one `--agent` |
| Skill loads but the advice doesn't fit | Skills can be imperfect. [Open an issue](https://github.com/NILANJAN-01/skill-hub/issues) with the prompt you used |

## Licenses

The `git-*` skills come from the *Pro Git* book and are **CC BY-NC-SA 3.0**: free to use and share for non-commercial purposes, and changes must use the same license. Every skill states its license in its `SKILL.md`.

## Want to add your own skill?

See [CONTRIBUTING.md](CONTRIBUTING.md). If you use an AI agent to help, it follows [AGENTS.md](AGENTS.md).
