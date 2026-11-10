---
name: git-first-time-git-setup
description: "First-Time Git Setup playbook extracted from \"Pro Git\". The first thing you should do when you install Git is to set your user name and email address. Use when the user asks about first-time git setup, git config, windows system, git environment, editor, user, option; or mentions git config --global, git config --list --show-origin, git config --list, git config, git config --show-origin."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "First-Time Git Setup"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "27-30"
---

# First-Time Git Setup

The first thing you should do when you install Git is to set your user name and email address.

_Built from "Pro Git" (pages 27-30) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **first-time git setup** (git config, windows system, git environment, editor, user).
- The user wants to run or understand `git config --global`.
- The user wants to run or understand `git config --list --show-origin`.
- The user wants to run or understand `git config --list`.
- The user wants to run or understand `git config`.

## When NOT to use

- For setup and config, use the `git-setup-and-config` skill instead.
- For git configuration, use the `git-configuration` skill instead.
- For environment variables, use the `git-environment-variables` skill instead.

## Key concepts

- If you pass the option `--system` to `git config`, it reads and writes from this file specifically.
- 2.`~/.gitconfig` or `~/.config/git/config` file: Values specific personally to you, the user.
- You can make Git read and write to this file specifically by passing the `--global` option, and this affects all of the repositories you work with on your system.
- On Windows systems, Git looks for the `.gitconfig` file in the `$HOME` directory (`C:\Users\$USER` for most people).
- This config file can only be changed by `gitconfig -f <file>` as an admin.
- If not configured, Git uses your system’s default editor.
- You may see keys more than once, because Git reads the same key from different files (`[path]/etc/gitconfig` and `~/.gitconfig`, for example).

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- **Warning (from source):** You may find, if you don’t setup your editor like this, you get into a really confusing state when Git attempts to launch it. An example on a Windows system may include a prematurely terminated Git operation during a Git initiated edit.
- You can force Git to read from and write to this file with the `--local` option, but that is in fact the default.

## Procedures

### First-Time Git Setup

**Goal:** You can also change them at any time by running through the commands again.

**Steps:**

1. You can view all of your settings and where they are coming from using:
   ```bash
   git config --list --show-origin
   ```

### Your Identity

**Goal:** The first thing you should do when you install Git is to set your user name and email address.

**Steps:**

1. This is important because every Git commit uses this information, and it’s immutably baked into the commits you start creating:
   ```bash
   git config --global user.name "John Doe"
   git config --global user.email johndoe@example.com
   ```

### Your Editor

**Goal:** In the case of Notepad++, a popular programming editor, you are likely to want to use the 32-bit version, since at the time of writing the 64-bit version doesn’t support all plug-ins.

**Steps:**

1. If you want to use a different text editor, such as Emacs, you can do the following:
   ```bash
   git config --global core.editor emacs
   ```
2. 32-bit Windows system, or you have a 64-bit editor on a 64-bit system, you’ll type something like this:
   ```bash
   git config --global core.editor "'C:/Program Files/Notepad++/notepad++.exe'
   ```
   Expected output (excerpt):
   ```text
   -multiInst -notabbar -nosession -noPlugin"
   ```

### Your default branch name

**Goal:** Your default branch name

**Steps:**

1. To set main as the default branch name do:
   ```bash
   git config --global init.defaultBranch main
   ```

### Checking Your Settings

**Goal:** Checking Your Settings

**Steps:**

1. If you want to check your configuration settings, you can use the `git config --list` command to list all the settings Git can find at that point:
   ```bash
   git config --list
   ```
   Expected output (excerpt):
   ```text
   user.name=John Doe
   user.email=johndoe@example.com
   color.status=auto
   color.branch=auto
   ```
2. You can also check what Git thinks a specific key’s value is by typing `git config <key>`:
   ```bash
   git config user.name
   ```
   Expected output (excerpt):
   ```text
   John Doe
   ```
3. Run:
   ```bash
   git config --show-origin rerere.autoUpdate
   ```
   Expected output (excerpt):
   ```text
   file:/home/johndoe/.gitconfig   false
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git config --global` | This is important because every Git commit uses this information, and it’s immutably baked into the commits you start creating | `git config --global core.editor emacs` |
| `git config --list --show-origin` | You can view all of your settings and where they are coming from using | `git config --list --show-origin` |
| `git config --list` | If you want to check your configuration settings, you can use the `git config --list` command to list all the settings Git can find at that point | `git config --list` |
| `git config` | If you want to check your configuration settings, you can use the `git config --list` command to list all the settings Git can find at that point | `git config user.name` |
| `git config --show-origin` | You can also check what Git thinks a specific key’s value is by typing `git config <key>` | `git config --show-origin rerere.autoUpdate` |

## Troubleshooting

- **Note:** Vim, Emacs and Notepad++ are popular text editors often used by developers on Unix-based systems like Linux and macOS or a Windows system. If you are using
- **Note:** Since Git might read the same configuration variable value from more than one file, it’s possible that you have an unexpected value for one of these values and you don’t know why. In cases like that, you can query Git as to the origin for that value, and it will tell you which configuration file had the final say in setting that value:

## Related skills

- `git-setup-and-config` - Setup and Config
- `git-configuration` - Git Configuration
- `git-environment-variables` - Environment Variables
- `git-getting-git-on-a-server` - Getting Git on a Server

## Source

"Pro Git", pages 27-30. Sections: First-Time Git Setup; First-Time Git Setup > Your Identity; First-Time Git Setup > Your Editor; First-Time Git Setup > Your default branch name; First-Time Git Setup > Checking Your Settings.
