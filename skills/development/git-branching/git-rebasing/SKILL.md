---
name: git-rebasing
description: "Rebase a branch (git rebase, --onto), rebase vs merge, fix pushed rebases. Use when handling rebasing or a linear history."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Rebasing"
  category: git-branching
  source: "Pro Git, 2nd edition"
  pages: "101-110"
---

# Rebasing

In Git, there are two main ways to integrate changes from one branch into another: the `merge` and the `rebase`.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git rebase master`
  - `git rebase --onto master server client`
  - `git rebase master server`
- If someone on your team force pushes changes that overwrite work that you’ve based work on, your challenge is to figure out what is yours and what they’ve rewritten.

## Commands

- `git checkout`: `git checkout master`
- `git merge`: `git merge client`
- `git rebase`: `git rebase master`
- `git branch -d`: `git branch -d client`
- `git rebase --onto`: `git rebase --onto master server client`

## Related skills

- `git-rewriting-history` - Rewriting History
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-advanced-merging` - Advanced Merging

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 101-110, CC BY-NC-SA 3.0._
