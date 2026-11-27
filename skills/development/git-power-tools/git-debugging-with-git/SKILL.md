---
name: git-debugging-with-git
description: "Find which commit broke something with git blame and git bisect. Use when asked who changed a line or what introduced a bug."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Debugging with Git"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "301-304"
---

# Debugging with Git

If you track down a bug in your code and want to know when it was introduced and why, file annotation is often your best tool.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git bisect`: `git bisect bad`
- `git blame -L`: `git blame -L 69,82 Makefile`
- `git blame -C -L`: `git blame -C -L 141,153 GITPackUpload.m`

## Related skills

- `git-searching` - Searching
- `git-as-a-client` - Git as a Client
- `git-advanced-merging` - Advanced Merging
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 301-304, CC BY-NC-SA 3.0._
