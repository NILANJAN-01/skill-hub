---
name: git-basic-snapshotting
description: "Quick reference for git add, status, diff, commit, reset, rm, mv. Use when asked which git command stages, commits or removes files."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Basic Snapshotting"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "487-489"
---

# Basic Snapshotting

For the basic workflow of staging content and committing it to your history, there are only a few basic commands.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- The `git commit` command takes all the file contents that have been staged with `git add` and records a new permanent snapshot in the database and then moves the branch pointer on the current branch up to it.
- This final option makes it possible for this command to lose your work if used incorrectly, so make sure you understand it before using it.

## Related skills

- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-basic-branching-and-merging` - Basic Branching and Merging
- `git-interactive-staging` - Interactive Staging
- `git-undoing-things` - Undoing Things

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 487-489, CC BY-NC-SA 3.0._
