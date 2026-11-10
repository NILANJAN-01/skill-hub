---
name: git-plumbing-and-porcelain
description: "Plumbing and Porcelain playbook extracted from \"Pro Git\". These commands are generally referred to as Git’s “plumbing” commands, while the more user-friendly commands are called “porcelain” Use when the user asks about plumbing and porcelain, full user-friendly vcs, version control system, initially a toolkit, number of subcommands, low-level work, chained together unix-style; or mentions ls -F1."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Plumbing and Porcelain"
  category: git-internals
  source: "Pro Git, 2nd edition"
  pages: "420-421"
---

# Plumbing and Porcelain

These commands are generally referred to as Git’s “plumbing” commands, while the more user-friendly commands are called “porcelain”

_Built from "Pro Git" (pages 420-421) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **plumbing and porcelain** (full user-friendly vcs, version control system, initially a toolkit, number of subcommands, low-level work).
- The user wants to run or understand `ls -F1`.

## When NOT to use

- For getting a git repository, use the `git-getting-a-git-repository` skill instead.
- For git objects, use the `git-objects` skill instead.
- For git hooks, use the `git-hooks` skill instead.

## Key concepts

- But because Git was initially a toolkit for a version control system rather than a full user-friendly VCS, it has a number of subcommands that do low-level work and were designed to be chained together UNIX-style or called from scripts.
- When you run `git init` in a new or existing directory, Git creates the `.git` directory, which is where almost everything that Git stores and manipulates is located.
- Depending on your version of Git, you may see some additional content there, but this is a fresh `gitinit` repository — it’s what you see by default.
- The `config` file contains your project-specific configuration options, and the `info` directory keeps a global exclude file for ignored patterns that you don’t want to track in a `.gitignore` file.
- The `hooks` directory contains your client- or server-side hook scripts, which are discussed in detail in Git Hooks.
- This leaves four important entries: the `HEAD` and (yet to be created) `index` files, and the `objects` and `refs` directories.
- The `objects` directory stores all the content for your database, the `refs` directory stores pointers into commit objects in that data (branches, tags, remotes and more), the `HEAD` file points to the branch you currently have checked out, and the `index` file is where Git stores your staging area information.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Plumbing and Porcelain

**Goal:** These commands are generally referred to as Git’s “plumbing” commands, while the more user-friendly commands are called “porcelain”

**Steps:**

1. Here’s what a newly-initialized `.git` directory typically looks like:
   ```bash
   ls -F1
   ```
   Expected output (excerpt):
   ```text
   config
   description
   HEAD
   ```
2. Run:
   ```text
   hooks/
   info/
   objects/
   refs/
   ```

## Related skills

- `git-getting-a-git-repository` - Getting a Git Repository
- `git-objects` - Git Objects
- `git-hooks` - Git Hooks
- `git-as-a-client` - Git as a Client

## Source

"Pro Git", pages 420-421. Sections: Plumbing and Porcelain.
