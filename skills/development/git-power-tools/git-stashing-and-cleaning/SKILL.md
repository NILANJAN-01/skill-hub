---
name: git-stashing-and-cleaning
description: "Shelve work with git stash and remove untracked files with git clean. Use when you need to switch branches with uncommitted changes."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Stashing and Cleaning"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "236-242"
---

# Stashing and Cleaning

The answer to this issue is the `git stash` command.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git stash drop stash@{0}`
- You’ll want to be pretty careful with this command, since it’s designed to remove files from your working directory that are not tracked.
- 'force' or “really do this,” and is required if the Git configuration variable `clean.requireForce` is not explicitly set to false.
- The other way you can be careful about the process is to run it with the `-i` or “interactive” flag.

## Commands

- `git stash`
- `git status -s`
- `git status`
- `git clean -n -d`
- `git stash --index`: `git stash apply --index`
- `git stash --keep-index`
- `git stash -u`
- `git stash --patch`
- `git clean -d -n`
- `git clean -x -i`

## Troubleshooting

- **Note:** Migrating to `git stash push` As of late October 2017, there has been extensive discussion on the Git mailing list, wherein the command `git stash save` is being deprecated in favour of the existing alternative `git stash push`. The main reason for this is that `git stash push` introduces the option of stashing selected pathspecs, something `git stash save` does not support.
- **Note:** There is a quirky situation where you might need to be extra forceful in asking Git to clean your working directory. If you happen to be in a working directory under which you’ve copied or cloned other Git repositories (perhaps as submodules), even `git clean -fd` will refuse to delete those directories. In cases like that, you need to add a second `-f` option for emphasis.

## Related skills

- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-basic-branching-and-merging` - Basic Branching and Merging
- `git-interactive-staging` - Interactive Staging
- `git-advanced-merging` - Advanced Merging

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 236-242, CC BY-NC-SA 3.0._
