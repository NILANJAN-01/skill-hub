---
name: git-setup-and-config
description: "Setup and Config playbook extracted from \"Pro Git\". There are two commands that are used quite a lot, from the first invocations of Git to common every day tweaking and referencing, the config and help commands. Use when the user asks about setup and config, tweaking and referencing, common every day, day tweaking, command, git setup, default."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Setup and Config"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "484-486"
---

# Setup and Config

There are two commands that are used quite a lot, from the first invocations of Git to common every day tweaking and referencing, the `config` and `help` commands.

_Built from "Pro Git" (pages 484-486) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **setup and config** (tweaking and referencing, common every day, day tweaking, command, git setup).

## When NOT to use

- For first-time git setup, use the `git-first-time-git-setup` skill instead.
- For git configuration, use the `git-configuration` skill instead.
- For credential storage, use the `git-credential-storage` skill instead.

## Key concepts

- Git has a default way of doing hundreds of things.
- For a lot of these things, you can tell Git to default to doing them a different way, or set your preferences.
- In First-Time Git Setup we used it to specify our name, email address and editor preference before we even got started using Git.
- `Text 3\sublime_text.exe' -w"` (Also see note below)
- `5\TextPad.exe' -m"` (Also see note below)
- The `git help` command is used to show you all the documentation shipped with Git about any command.
- We introduced the `git help` command in Getting Help and showed you how to use it to find more information about the `git shell` in Setting Up the Server.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### git config core.editor commands

**Goal:** git config core.editor commands

**Steps:**

1. Atom
   ```text
   git config --global core.editor "atom --wait"
   git config --global core.editor "bbedit -w"
   ```
2. Emacs
   ```text
   git config --global core.editor emacs
   ```
3. Gedit (Linux)
   ```text
   git config --global core.editor "gedit --wait --new-window"
   ```
4. Gvim (Windows 64-bit)
   ```text
   git config --global core.editor "'C:\Program
   ```
5. Helix
   ```text
   git config --global core.editor "hx"
   ```
6. Kate (Linux)
   ```text
   git config --global core.editor "kate --block"
   ```

_14 more step(s) in references/procedures.md._

More procedures in [references/procedures.md](references/procedures.md):

- git config core.editor commands

## Decision guide

- For a lot of these things, you can tell Git to default to doing them a different way, or set your preferences.
- This involves everything from telling Git what your name is to specific terminal color preferences or what editor you use.
- In First-Time Git Setup we used it to specify our name, email address and editor preference before we even got started using Git.

## Troubleshooting

- **Note:** If you have a 32-bit editor on a Windows 64-bit system, the program will be installed in `C:\Program Files (x86)\` rather than `C:\Program Files\` as in the table above.

## Related skills

- `git-first-time-git-setup` - First-Time Git Setup
- `git-configuration` - Git Configuration
- `git-credential-storage` - Credential Storage
- `git-aliases` - Git Aliases

## Source

"Pro Git", pages 484-486. Sections: Setup and Config; Setup and Config > git config; Setup and Config > git config core.editor commands; Setup and Config > git help.
