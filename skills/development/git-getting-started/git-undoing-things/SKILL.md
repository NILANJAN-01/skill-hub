---
name: git-undoing-things
description: "Undo git mistakes: amend, unstage, discard changes (restore, reset). Use when committed too early or staged the wrong file."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Undoing Things"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "52-56"
---

# Undoing Things

One of the common undos takes place when you commit too early and possibly forget to add some files, or you mess up your commit message.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git commit --amend`
  - `git checkout -- CONTRIBUTING.md`
  - `git restore CONTRIBUTING.md`
- **Note (from source):** It’s important to understand that when you’re amending your last commit, you’re not so much fixing it as replacing it entirely with a new, improved commit that pushes the old commit out of the way and puts the new commit in its place. Effectively, it’s as if the previous commit never happened, and it won’t show up in your repository history.
- **Note (from source):** Only amend commits that are still local and have not been pushed somewhere. Amending previously pushed commits and force pushing the branch will cause problems for your collaborators. For more on what happens when you do this and how to recover if you’re on the receiving end read The Perils of Rebasing.
- **Note (from source):** It’s true that `git reset` can be a dangerous command, especially if you provide the `--hard` flag. However, in the scenario described above, the file in your working directory is not touched, so it’s relatively safe.

## Commands

- `git status`
- `git add`: `git add *`
- `git commit --amend`
- `git commit -m`: `git commit -m 'Initial commit'`
- `git reset`: `git reset HEAD CONTRIBUTING.md`
- `git checkout`: `git checkout -- CONTRIBUTING.md`
- `git restore --staged`: `git restore --staged CONTRIBUTING.md`
- `git restore`: `git restore CONTRIBUTING.md`

## Related skills

- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-reset-demystified` - Reset Demystified
- `git-interactive-staging` - Interactive Staging
- `git-rewriting-history` - Rewriting History

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 52-56, CC BY-NC-SA 3.0._
