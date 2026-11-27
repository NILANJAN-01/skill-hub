---
name: git-plumbing-and-porcelain
description: "What is inside .git and plumbing vs porcelain commands. Use when asked what the .git folder contains."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Plumbing and Porcelain"
  category: git-internals
  source: "Pro Git, 2nd edition"
  pages: "420-421"
---

# Plumbing and Porcelain

These commands are generally referred to as Git’s “plumbing” commands, while the more user-friendly commands are called “porcelain”

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Related skills

- `git-getting-a-git-repository` - Getting a Git Repository
- `git-objects` - Git Objects
- `git-hooks` - Git Hooks
- `git-as-a-client` - Git as a Client

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 420-421, CC BY-NC-SA 3.0._
