---
name: git-working-with-remotes
description: "Manage git remotes: add, show, fetch, pull, push, rename, remove. Use when you need to add or change a remote URL."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Working with Remotes"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "56-61"
---

# Working with Remotes

To see which remote servers you have configured, you can run the `git remote` command.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git remote`
- `git remote -v`
- `git fetch`: `git fetch pb`
- `git clone`: `git clone https://github.com/schacon/ticgit`
- `git push`: `git push origin master`

## Troubleshooting

- **Note:** Remote repositories can be on your local machine. It is entirely possible that you can be working with a “remote” repository that is, in fact, on the same host you are. The word “remote” does not necessarily imply that the repository is somewhere else on the network or Internet, only that it is
- **Note:** From Git version 2.27 onward, `git pull` will give a warning if the `pull.rebase` variable is not set. Git will keep warning you until you set the variable.

## Related skills

- `git-remote-branches` - Remote Branches
- `git-the-refspec` - The Refspec
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-branch-management` - Branch Management

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 56-61, CC BY-NC-SA 3.0._
