---
name: git-remote-branches
description: "Push branches, track upstreams, fetch vs pull, delete remote branches. Use when handling origin/<branch> tasks."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Remote Branches"
  category: git-branching
  source: "Pro Git, 2nd edition"
  pages: "91-101"
---

# Remote Branches

Checking out a local branch from a remote-tracking branch automatically creates what is called a “tracking branch” (and the branch it tracks is called an “upstream branch”).

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git push origin --delete serverfix`
- **Note (from source):** Don’t type your password every time If you’re using an HTTPS URL to push over, the Git server will ask you for your username and password for authentication. By default it will prompt you on the terminal for this information so the server can tell if you’re allowed to push.

## Commands

- `git checkout -b`: `git checkout -b sf origin/serverfix`
- `git push`: `git push origin serverfix`
- `git fetch`: `git fetch origin`
- `git checkout --track`: `git checkout --track origin/serverfix`
- `git checkout`: `git checkout serverfix`
- `git branch -u`: `git branch -u origin/serverfix`
- `git branch -vv`
- `git fetch -vv`: `git fetch --all; git branch -vv`
- `git push --delete`: `git push origin --delete serverfix`

## Troubleshooting

- **Note:** “origin” is not special Just like the branch name “master” does not have any special meaning in Git, neither does “origin”. While “master” is the default name for a starting branch when you run `git init` which is the only reason it’s widely used, “origin” is the default name for a remote when you run `git clone`. If you run `git clone -o booyah` instead, then you will have `booyah/master` as your default remote branch.
- **Note:** Upstream shorthand When you have a tracking branch set up, you can reference its upstream branch with the `@{upstream}` or `@{u}` shorthand. So if you’re on the `master` branch and it’s tracking `origin/master`, you can say something like `git merge @{u}` instead of `gitmerge origin/master` if you wish.

## Related skills

- `git-working-with-remotes` - Working with Remotes
- `git-the-refspec` - The Refspec
- `git-branch-management` - Branch Management
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 91-101, CC BY-NC-SA 3.0._
