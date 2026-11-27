---
name: git-aliases
description: "Create git command shortcuts with git config alias. Use when the user wants a git alias or shorter commands."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git Aliases"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "66-68"
---

# Git Aliases

As you go on using Git, you’ll probably use other commands frequently as well; don’t hesitate to create new aliases.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git config --global`: `git config --global alias.br branch`
- `git unstage`: `git unstage fileA`
- `git reset`: `git reset HEAD -- fileA`
- `git last`

## Related skills

- `git-reset-demystified` - Reset Demystified
- `git-configuration` - Git Configuration
- `git-undoing-things` - Undoing Things
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 66-68, CC BY-NC-SA 3.0._
