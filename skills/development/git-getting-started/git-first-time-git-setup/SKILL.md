---
name: git-first-time-git-setup
description: "Set up git on a new machine: user.name, email, editor, default branch. Use when handling first-time setup or Please tell me who you are."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "First-Time Git Setup"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "27-30"
---

# First-Time Git Setup

The first thing you should do when you install Git is to set your user name and email address.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- **Warning (from source):** You may find, if you don’t setup your editor like this, you get into a really confusing state when Git attempts to launch it. An example on a Windows system may include a prematurely terminated Git operation during a Git initiated edit.
- You can force Git to read from and write to this file with the `--local` option, but that is in fact the default.

## Commands

- `git config --global`: `git config --global core.editor emacs`
- `git config --list --show-origin`
- `git config --list`
- `git config`: `git config user.name`
- `git config --show-origin`: `git config --show-origin rerere.autoUpdate`

## Troubleshooting

- **Note:** Vim, Emacs and Notepad++ are popular text editors often used by developers on Unix-based systems like Linux and macOS or a Windows system. If you are using
- **Note:** Since Git might read the same configuration variable value from more than one file, it’s possible that you have an unexpected value for one of these values and you don’t know why. In cases like that, you can query Git as to the origin for that value, and it will tell you which configuration file had the final say in setting that value:

## Related skills

- `git-setup-and-config` - Setup and Config
- `git-configuration` - Git Configuration
- `git-environment-variables` - Environment Variables
- `git-getting-git-on-a-server` - Getting Git on a Server

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 27-30, CC BY-NC-SA 3.0._
