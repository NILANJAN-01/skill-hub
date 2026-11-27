---
name: git-interactive-staging
description: "Stage part of a file with git add -p or git add -i. Use when you need to commit only some changes or split a commit."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Interactive Staging"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "232-236"
---

# Interactive Staging

You can see that this command shows you a much different view of your staging area than you’re probably used to — basically, the same information you get with `git status` but a bit more succinct and informative.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git add -i`

## Related skills

- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-undoing-things` - Undoing Things
- `git-basic-snapshotting` - Basic Snapshotting
- `git-stashing-and-cleaning` - Stashing and Cleaning

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 232-236, CC BY-NC-SA 3.0._
