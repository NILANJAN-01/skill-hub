---
name: git-branches-in-a-nutshell
description: "Explain git branches, HEAD and commits as snapshots. Use when asked what a branch or HEAD is."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Branches in a Nutshell"
  category: git-branching
  source: "Pro Git, 2nd edition"
  pages: "69-76"
---

# Branches in a Nutshell

In Git, this is a pointer to the local branch you’re currently on.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- Because a branch in Git is actually a simple file that contains the 40 character SHA-1 checksum of the commit it points to, branches are cheap to create and destroy.

## Commands

- `git log --oneline --decorate`
- `git checkout`: `git checkout master`
- `git commit -a -m`: `git commit -a -m 'Make a change'`
- `git add`: `git add README test.rb LICENSE`
- `git commit -m`: `git commit -m 'Initial commit'`
- `git branch`: `git branch testing`

## Troubleshooting

- **Note:** The “master” branch in Git is not a special branch. It is exactly like any other branch. The only reason nearly every repository has one is that the `git init` command creates it by default and most people don’t bother to change it.
- **Note:** `git log` doesn’t show all the branches all the time

## Related skills

- `git-basic-branching-and-merging` - Basic Branching and Merging
- `git-references` - Git References
- `git-reset-demystified` - Reset Demystified
- `git-objects` - Git Objects

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 69-76, CC BY-NC-SA 3.0._
