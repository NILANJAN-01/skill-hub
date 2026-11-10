---
name: git-basic-snapshotting
description: "Basic Snapshotting playbook extracted from \"Pro Git\". For the basic workflow of staging content and committing it to your history, there are only a few basic commands. Use when the user asks about basic snapshotting, staging area, git add, git diff, git commit, staged, git reset."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Basic Snapshotting"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "487-489"
---

# Basic Snapshotting

For the basic workflow of staging content and committing it to your history, there are only a few basic commands.

_Built from "Pro Git" (pages 487-489) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **basic snapshotting** (staging area, git add, git diff, git commit, staged).
- We mention how to use it to resolve merge conflicts in Basic Merge Conflicts.

## When NOT to use

- For recording changes to the repository, use the `git-recording-changes-to-the-repository` skill instead.
- For basic branching and merging, use the `git-basic-branching-and-merging` skill instead.
- For interactive staging, use the `git-interactive-staging` skill instead.

## Key concepts

- The `git add` command adds content from the working directory into the staging area (or “index”) for the next commit.
- In its normal form, it also will show you some basic hints on how to move files between these stages.
- We first cover `status` in Checking the Status of Your Files, both in its basic and simplified forms.
- We first look at the basic uses of `git diff` in Viewing Your Staged and Unstaged Changes, where we show how to see what changes are staged and which are not yet staged.
- We first cover the basics of committing in Committing Your Changes.
- The `git rm` command is used to remove files from the staging area and working directory for Git.
- The `git mv` command is a thin convenience command to move a file and then run `git add` on the new file and `git rm` on the old file.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- The `git commit` command takes all the file contents that have been staged with `git add` and records a new permanent snapshot in the database and then moves the branch pointer on the current branch up to it.
- This final option makes it possible for this command to lose your work if used incorrectly, so make sure you understand it before using it.

## Decision guide

- There we also demonstrate how to use the `-a` flag to skip the `git add` step in daily workflows and how to use the `-m` flag to pass a commit message in on the command line instead of firing up an editor.

## Related skills

- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-basic-branching-and-merging` - Basic Branching and Merging
- `git-interactive-staging` - Interactive Staging
- `git-undoing-things` - Undoing Things

## Source

"Pro Git", pages 487-489. Sections: Basic Snapshotting; Basic Snapshotting > git add; Basic Snapshotting > git status; Basic Snapshotting > git diff; Basic Snapshotting > git difftool; Basic Snapshotting > git commit; Basic Snapshotting > git reset; Basic Snapshotting > git rm; Basic Snapshotting > git mv; Basic Snapshotting > git clean.
