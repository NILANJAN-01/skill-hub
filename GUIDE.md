# Using skill-hub: step-by-step guide

This guide takes you from nothing to working skills in your AI coding agents in about 5 minutes. The installer detects which agents you have and asks before changing anything. It works for **Claude Code, Google Antigravity, Devin, GitHub Copilot (VS Code), Cursor, Windsurf, OpenAI Codex and Gemini CLI**.

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

## Step 2: Run the installer. It finds your agents and asks you

Run the installer with **no options**. It works out which AI agents and IDEs are on your computer and asks what you want. **Nothing is written until you say yes.**

**macOS / Linux**

```bash
curl -fsSL https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py | python3 -
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py -OutFile install.py
python install.py
```

(If you have a clone of this repo, `python tools/install.py` does the same.)

It asks four questions:

```
Agents found on this machine:
  [x] Claude Code                  (command `claude`; ~/.claude)
  [x] GitHub Copilot (VS Code)     (~/.vscode; ...\Programs\Microsoft VS Code)
  [x] OpenAI Codex                 (~/.codex)
  Not found: Google Antigravity, Devin, Cursor, Windsurf (Devin Local), Gemini CLI

Which agents should get the skills?
   1) Claude Code
   2) GitHub Copilot (VS Code)
   3) OpenAI Codex
   4) Google Antigravity   (not detected)
   ...
Your choice (a = all 3 detected, numbers like 1,3 or 2-4, n = none): a

Which skills? (64 available)
   1) Everything (64 skills)
   2) git-skills              61 skills  All 61 Git skills ...
   4) git-branching            7 skills  Git branching & merging ...
   ...
Your choice (a = everything, numbers like 1,3 or 2-4, n = none): 4

Where?
   1) For me, in every project (user-level folders)  [default]
   2) Only this project: /home/you/my-project
Your choice [1/2]: 1

Plan:
  + install   7 skill(s) into ~/.claude/skills   (read by Claude Code, GitHub Copilot (VS Code))
  + install   7 skill(s) into ~/.agents/skills   (read by GitHub Copilot (VS Code), OpenAI Codex)

Go ahead? [Y/n] y
```

How to answer:

| Question | Answers |
|---|---|
| Agents | `a` = every **detected** agent · numbers such as `1,3` or `2-4` (you can also pick ones marked *not detected*) · `n` = stop |
| Skills | `a` = everything · numbers to pick categories, e.g. `4` or `3,4,11` · `n` = stop |
| Where | `1` = for you, in every project (default) · `2` = only the current project folder, which you can share through git |
| Go ahead? | `y` to install, `n` to cancel with nothing changed |

What the installer does for you:

- **Detects agents fresh on every run**, from installed apps, commands on your PATH and the agents' own config folders.
- **Avoids duplicates.** Some agents read several folders. Copilot, for example, also reads Claude Code's and Codex's folders. The installer writes to the fewest folders that cover everyone you picked, and skips skills an agent can already see.
- **Never overwrites without asking.** If an installed skill differs from the hub version (an update, or your own edits), it asks first. The default is **no**.
- **Offers to tidy up.** If an identical copy becomes redundant because another folder now covers it, it offers to remove it.
- **Is safe to run again.** A repeat run reports *"Nothing to do"*.

> **Tip:** Install only what you need. Every installed skill adds its description to your agent's context. To browse first, see [`skills/README.md`](skills/README.md) or [`examples/PROMPTS.md`](examples/PROMPTS.md).

## Step 3: Restart or reload your agents

Most agents scan for skills when a session starts:

- **IDEs** (Antigravity, Cursor, Windsurf, VS Code with Copilot): reload the window or open a new chat.
- **CLIs** (Claude Code, Codex, Gemini CLI, Devin CLI): start a new session.
- **Cloud Devin:** install into the project (answer `2` to *Where?*), then commit and push the `.agents/skills/` folder. Devin reads skills from the repo.

## Step 4: Use them by just asking

Describe your task normally. For example, after installing `git-rebasing`:

> *"My feature branch is behind main. Put my commits on top of the latest main without a merge commit."*

The agent matches your request to the skill and follows its steps. [`examples/PROMPTS.md`](examples/PROMPTS.md) has 3 ready-made prompts for every skill.

**Want to force a specific skill?** Name it:

> *"Use the git-hooks skill: block commits whose message doesn't start with a ticket ID."*

## Step 5: Check that it worked

- **Ask your agent:** *"Which skills do you have available?"* The installed skill names should appear.
- **Check the folders** listed in the plan from Step 2. Each should contain `<skill-name>/SKILL.md`.
- **If the agent answered without using the skill:** that can happen for simple questions the agent already knows well. Name the skill explicitly (Step 4) when you want its exact procedure.

## Step 6: Share it with your team (optional)

If you answered `2` (only this project), the skills are in folders inside your repo, such as `.agents/skills/` or `.claude/skills/`. Commit them:

```bash
git add .agents/skills .claude/skills     # whichever folders the plan listed
git commit -m "Add skill-hub skills"
git push
```

Everyone who clones the repo now gets the skills in their agent automatically.

## Step 7: Update or remove skills

- **Update:** run the installer again. It lists skills that differ from the hub and asks before replacing them.
- **Remove a skill:** delete its folder, for example `~/.claude/skills/git-rebasing/`.

---

## Do it in one command (no questions)

Use options when you already know what you want, or for scripts, dotfiles and CI. Replace `...` with `curl -fsSL <installer-url> | python3 -` (macOS/Linux) or `python install.py` (Windows / a clone).

```bash
... --detect                                         # just show which agents are installed
... --list                                           # agents, categories and every skill
... --agent detected --all --global                  # every skill, every detected agent, for you
... --agent cursor --skill git-rebasing              # one skill, one agent, this project
... --agent copilot,claude-code --plugin git-branching --global
... --agent codex --plugin git-skills --global --dry-run     # preview only
... --agent detected --all --global --yes            # no confirmation prompt (scripts)
... --agent detected --all --global --force --tidy   # also update changed skills and remove redundant copies
```

Agent IDs for `--agent`:

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
| Every agent found on this computer | `detected` |
| Something else that supports Agent Skills | `universal` |

Categories for `--plugin`:

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

`--all` installs every skill. `--skill a,b` installs specific skills by name.

---

## Example: all skills in VS Code (GitHub Copilot)

The full flow for one common setup: every hub skill, available in every folder you open in VS Code.

1. **Install all 64 skills** (the `git-skills` and `hub-tools` categories) into Copilot's personal folder:

   ```powershell
   # Windows PowerShell
   irm https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py -OutFile install.py
   python install.py --agent copilot --plugin git-skills,hub-tools --global
   ```
   ```bash
   # macOS / Linux
   curl -fsSL https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py | python3 - --agent copilot --plugin git-skills,hub-tools --global
   ```
   This writes to `~/.copilot/skills/` (on Windows, `C:\Users\<you>\.copilot\skills\`). For one repo only, drop `--global` and run it from the repo root. The skills then go to `.github/skills/`, which you can commit for your team.

2. **Reload VS Code:** `Ctrl+Shift+P` → **Developer: Reload Window** (or just open a new chat). No setting needs to be turned on.
3. **Check they loaded:** `Ctrl+Shift+P` → **Chat: Open Customizations** → **Skills**. You can also type `/` (or `/skills`) in the Copilot Chat box.
4. **Use them** in Copilot Chat (`Ctrl+Alt+I`), in chat or agent mode:
   - Just ask: *"My feature branch is behind main. Put my commits on top of main without a merge commit."*
   - Or pick a skill as a slash command: *"`/git-hooks` block commits whose message doesn't start with a ticket ID"*
5. **Update later** by running the installer again (it asks before replacing anything), or add `--force` to the command. Remove a skill by deleting its folder.

   Prefer to be asked? Run `python install.py` with no options, pick **GitHub Copilot (VS Code)** and **Everything**, then answer `1` to *Where?*.

> Copilot also reads `.agents/skills` and `.claude/skills` (and `~/.agents/skills`, `~/.claude/skills`). Don't install the same skill in more than one of them, or it shows up twice. If you also use Claude Code, Codex or another agent, name them all in one command (e.g. `--agent copilot,claude-code`) and the installer avoids duplicates.

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
| On Windows, `curl ... \| python3 -` fails | Use the PowerShell commands from Step 2 (`irm ... -OutFile install.py`, then `python install.py`) |
| `differ from the hub` in the plan | The installed copy is older or was edited locally. Answer `y` to replace it, or add `--force` |
| `No terminal available for questions` | You ran it somewhere it can't ask questions (CI, scripts). Use options instead, e.g. `--agent detected --all --global --yes` |
| My agent isn't detected | Pick it by number anyway (it's listed as *not detected*), or pass `--agent <id>`. Detection looks for the app, its command, or its config folder |
| `will find N skill(s) in more than one folder` | Some agents read each other's folders (e.g. Copilot reads Claude Code's and Codex's). With that mix of agents a second copy can't be avoided. It's harmless, but the skill may be listed twice |
| `Unknown skill` / `Unknown plugin` | Check the spelling with `--list` |
| `unknown agent` | Use one of the IDs from [the table above](#do-it-in-one-command-no-questions) |
| Download fails or times out | Check your internet or proxy, or clone the repo and run `python tools/install.py ...` from it |
| Agent doesn't see the skill | Restart or reload it (Step 3). For project installs, check that you ran the installer from the project root |
| The same skill appears twice | It's in two folders your agent reads. Run the installer again and accept *Remove the redundant identical copies?*, or delete one copy |
| Skill loads but the advice doesn't fit | Skills can be imperfect. [Open an issue](https://github.com/NILANJAN-01/skill-hub/issues) with the prompt you used |

## Licenses

The `git-*` skills come from the *Pro Git* book and are **CC BY-NC-SA 3.0**: free to use and share for non-commercial purposes, and changes must use the same license. Every skill states its license in its `SKILL.md`.

## Want to add your own skill?

See [CONTRIBUTING.md](CONTRIBUTING.md). If you use an AI agent to help, it follows [AGENTS.md](AGENTS.md).
