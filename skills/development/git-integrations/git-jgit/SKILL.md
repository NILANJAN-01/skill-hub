---
name: git-jgit
description: "Use git from Java with the JGit library. Use when writing Java code that reads or changes a git repository."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "JGit"
  category: git-integrations
  source: "Pro Git, 2nd edition"
  pages: "477-480"
---

# JGit

JGit is a relatively full-featured implementation of Git written natively in Java, and is widely used in the Java community.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Related skills

- `git-libgit2` - Libgit2
- `git-as-a-client` - Git as a Client
- `git-scripting-github` - Scripting GitHub
- `git-plumbing-and-porcelain` - Plumbing and Porcelain

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 477-480, CC BY-NC-SA 3.0._
