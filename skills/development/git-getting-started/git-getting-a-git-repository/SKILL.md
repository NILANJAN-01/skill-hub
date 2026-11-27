---
name: git-getting-a-git-repository
description: "Start a repository with git init or git clone. Use when you need to create a repo, put a project under git, or clone one."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Getting a Git Repository"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "32-34"
---

# Getting a Git Repository

This is an important distinction — instead of getting just a working copy, Git receives a full copy of nearly all data that the server has.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git add`: `git add *.c`
- `git clone`: `git clone https://github.com/libgit2/libgit2`
- `git init`
- `git commit -m`: `git commit -m 'Initial project version'`

## Related skills

- `git-getting-git-on-a-server` - Getting Git on a Server
- `git-the-protocols` - The Protocols
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-submodules` - Submodules

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 32-34, CC BY-NC-SA 3.0._
