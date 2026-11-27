---
name: git-setup-and-config
description: "Quick reference for git config and git help, including core.editor for common editors. Use when you need to set the git editor."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Setup and Config"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "484-486"
---

# Setup and Config

There are two commands that are used quite a lot, from the first invocations of Git to common every day tweaking and referencing, the `config` and `help` commands.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Troubleshooting

- **Note:** If you have a 32-bit editor on a Windows 64-bit system, the program will be installed in `C:\Program Files (x86)\` rather than `C:\Program Files\` as in the table above.

## Related skills

- `git-first-time-git-setup` - First-Time Git Setup
- `git-configuration` - Git Configuration
- `git-credential-storage` - Credential Storage
- `git-aliases` - Git Aliases

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 484-486, CC BY-NC-SA 3.0._
