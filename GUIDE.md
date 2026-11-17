# Using skill-hub: step-by-step guide

> Looking for everything in one place (every skill, script, installer option, agent and MCP tool)? Open the generated **[user guide](user-guide.html)** in a browser.

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

**Fastest: one command for everything.** `--setup` installs every skill and the skill-hub MCP server into every agent it finds, for your user. It shows the plan first; **nothing is written until you say yes.**

```bash
curl -fsSL https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py | python3 - --setup   # macOS / Linux
python install.py --setup                                                                                     # Windows, after the download below
```

Later, `python install.py --doctor` shows what is set up for each agent and checks that the MCP server starts, and `python install.py --uninstall` removes everything the installer set up.

**Prefer to choose?** Run the installer with **no options**. It works out which AI agents and IDEs are on your computer and offers a menu: set up everything, choose agents and skills, check, or remove. **Nothing is written until you say yes.**

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

**Windows, one shot:** from a clone, double-click or run `install.bat`. It checks Python 3.8+, that your profile folder is writable, and that the installer can be found (it downloads `tools/install.py` if you only have the `.bat`), lists the agents it detects, then installs every skill into every detected agent for your user. It shows the plan and asks `y/n` first. `install.bat --check` only checks; `install.bat --yes` skips the question; any other options (for example `--plugin hub-tools --agent claude-code`) go straight to the installer.

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

Which skills? (every skill in the hub)
   1) Everything
   2) git-skills              61 skills  All Git skills ...
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

- **Check everything:** `python install.py --doctor` lists, per agent, how many hub skills it has (and which differ from the hub), whether the MCP server is registered, and runs a self-check of the server.
- **See what is installed:** `python install.py --installed --global` lists every hub skill, the hub version it came from, and whether it still matches the hub. (Drop `--global` for the current project.)
- **Add other MCP servers to every agent:** `python install.py --list-mcp` shows the presets; `python install.py --add-mcp playwright --mcp-test` tests the server, then adds it to every detected agent. Use `--mcp-command "<command> <args>"` for any other server, `--mcp-env NAME` to copy a secret from your environment, and `--remove-mcp <name>` to take it out again.
- **Remove everything:** `python install.py --uninstall` removes the hub skills, the `skill-hub` MCP entries and the hub copy in `~/.skill-hub`. It lists everything and asks first.
- **Update:** run the installer again, or add `--update`. It compares every file of a skill (not only `SKILL.md`), lists the skills that differ from the hub and asks before replacing them.
- **Remove a skill:** `python install.py --agent <agent> --skill <name> --global --remove`. It lists the copies it found and asks first. Deleting the folder by hand also works.
- **Stay on one version:** use the installer from a [release](https://github.com/NILANJAN-01/skill-hub/releases), or pass `--ref v1.3.0` (or set `SKILLHUB_REF`). Release downloads are checked against the release's `SHA256SUMS`.

---

## Do it in one command (no questions)

Use options when you already know what you want, or for scripts, dotfiles and CI. Replace `...` with `curl -fsSL <installer-url> | python3 -` (macOS/Linux) or `python install.py` (Windows / a clone).

```bash
... --setup --yes                                    # everything: all skills + MCP server, every detected agent
... --agent detected --mcp --global                  # only the skill-hub MCP server
... --detect                                         # just show which agents are installed
... --list                                           # agents, categories and every skill
... --agent detected --all --global                  # every skill, every detected agent, for you
... --agent cursor --skill git-rebasing              # one skill, one agent, this project
... --agent copilot,claude-code --plugin git-branching --global
... --agent codex --plugin git-skills --global --dry-run     # preview only
... --agent detected --all --global --yes            # no confirmation prompt (scripts)
... --agent detected --all --global --force --tidy   # also update changed skills and remove redundant copies
... --installed --global                             # what is installed, and from which hub version
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

<!-- plugins-simple:start -->
<!-- Generated by tools/build_catalog.py -->
| Category | Skills | What's in it |
|---|---:|---|
| `git-skills` | 61 | All 61 Git skills extracted from the Pro Git book (bundle of every git-* plugin) |
| `git-getting-started` | 11 | Git fundamentals: install and configure Git, create repositories, record changes, view history, undo mistakes, tags and aliases |
| `git-branching` | 7 | Git branching & merging: branches, merging, remote-tracking branches, rebasing, advanced merge conflicts and rerere |
| `git-collaboration` | 14 | Collaborating with Git: remotes, protocols, hosting a Git server (SSH, daemon, Smart HTTP, GitWeb), distributed workflows, GitHub and credentials |
| `git-power-tools` | 11 | Git power tools: revision selection, interactive staging, stash, signing, searching, rewriting history, reset, bisect/blame, submodules, bundles and replace |
| `git-customization` | 5 | Customizing Git: configuration, attributes, client/server hooks, enforced policies and environment variables |
| `git-internals` | 7 | Git internals: plumbing commands, objects, references, packfiles, refspecs, transfer protocols, maintenance and data recovery |
| `git-integrations` | 5 | Git with other systems and tools: Git as an SVN/Mercurial/Perforce client, migrating to Git, PowerShell, JGit and libgit2 |
| `git-reference` | 1 | Full Pro Git reference skill: chapter-by-chapter source knowledge for Git questions no focused skill covers |
| `android-automation` | 2 | Android test automation and debugging: generate keyword/resource-id locator JSON from the screen of a device or a UIAutomator XML dump (including automotive OEM head... |
| `adb-tools` | 4 | ADB (Android Debug Bridge) skill set from the official docs: adb-tool is the central skill with all 139 commands, risk levels and one Python script; adb-connect sets... |
| `gradle-tools` | 1 | Gradle for Android: set up the wrapper, JDK, SDK and version catalog, check JDK/Gradle/AGP/Kotlin compatibility, diagnose build failures from a log, add libraries,... |
| `repo-tools` | 2 | Repositories: read a whole codebase file by file and write a LEARNINGS.md, with a script that plans the read and checks nothing was missed; draw the architecture as... |
| `image-tools` | 1 | Images: read any PNG/JPG/WebP/GIF/BMP with a Python script and report pixels (exact colours, regions, palette, pixel map, CSV) plus a plain-text description, EXIF and... |
| `video-tools` | 1 | Video: analyse MP4/MOV/MKV/WebM with a Python script - metadata, frames extracted as images, per-frame colours, brightness and motion, scenes, black and frozen... |
| `hub-tools` | 6 | Skills for working with the hub itself: find and install skills, contribute new skills, generate skills from technical PDFs (skillforge) and from web pages... |
| `testing-tools` | 2 | Testing: write, run and verify Kotlin unit tests class by class and method by method with Python scripts - Gradle/Maven/kotlinc runs, test-to-method mapping, quality... |
| `gitlab-ci-tools` | 3 | GitLab CI/CD: write .gitlab-ci.yml pipelines, debug failing or stuck pipelines, and make pipelines faster and cheaper |
| `writing-tools` | 1 | Writing: prepare blog posts, CVs (tailor to a job post, review), cover letters and technical docs, with templates and a checker script |
| `shell-tools` | 1 | Shell: run files, text, process, network, Git and build tasks correctly in PowerShell on Windows, with a bash-to-PowerShell map and troubleshooting |
| `learning-tools` | 1 | Learning: explain any Python file from beginner to advanced and generate study-notes HTML for interview preparation (concepts, gotchas, Q&A, fundamentals checklist) |
| `youtube-tools` | 1 | YouTube: extract a study or tech video's audio, analyse it (speech, pauses, pace) and turn the speech into text, then make text notes and a easy-to-read HTML overview... |
| `ai-efficiency-tools` | 3 | AI efficiency: audit a project for token waste, save tokens and cost, measure how many tokens each skill saves (central ledger and report), and centralize context... |
| `ai-agent-tools` | 4 | AI agents: build and probe MCP servers, design tool/function definitions models use well, run LLM evals with regression checks, and build and evaluate RAG pipelines,... |
| `playwright-tools` | 5 | Playwright (up to 1.65): write resilient end-to-end tests that fit your team's conventions (with a suite audit script), debug failing and flaky tests from JSON or... |
| `robotframework-tools` | 4 | Robot Framework (up to 7.5): write and modernise suites with VAR, typed and secret variables, GROUP, test metadata and Markdown tests (with an audit script), build... |
<!-- plugins-simple:end -->

`--all` installs every skill. `--skill a,b` installs specific skills by name.

---

## Example: all skills in VS Code (GitHub Copilot)

The full flow for one common setup: every hub skill, available in every folder you open in VS Code.

1. **Install the Git skills and the hub tools** (the `git-skills` and `hub-tools` categories) into Copilot's personal folder:

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

Download or clone the repo and copy a skill's folder into your agent's folder. In the repo a skill is at `skills/<area>/<group>/<name>/` ([skills/README.md](skills/README.md) links every one); copy only the last part, `<name>/`:

<!-- agents-simple:start -->
<!-- Generated by tools/build_catalog.py -->
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
| On Windows, `curl ... \| python3 -` fails | In Command Prompt use `python` (not `python3`): `curl -fsSL <url> \| python -`. In PowerShell use the commands from Step 2 (`irm ... -OutFile install.py`, then `python install.py`) |
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
