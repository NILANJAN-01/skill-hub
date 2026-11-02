---
name: git-remote-branches
description: "Remote Branches playbook extracted from \"Pro Git\". Checking out a local branch from a remote-tracking branch automatically creates what is called a “tracking branch” (and the branch it tracks is called an “upstream branch”). Use when the user asks about remote branches, remote branch, local branch, git fetch, remote-tracking branch, git server, git branch; or mentions git branch -u, git branch -vv, git checkout -b, git push, git fetch, git checkout --track."
---

# Remote Branches

Checking out a local branch from a remote-tracking branch automatically creates what is called a “tracking branch” (and the branch it tracks is called an “upstream branch”).

_Built from "Pro Git" (pages 91-101) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **remote branches** (remote branch, local branch, git fetch, remote-tracking branch, git server).
- The user wants to run or understand `git branch -u`.
- The user wants to run or understand `git branch -vv`.
- The user wants to run or understand `git checkout -b`.
- The user wants to run or understand `git push`.
- When you want to share a branch with the world, you need to push it up to a remote to which you have write access.
- That way, you can use private branches for work you don’t want to share, and push up only the topic branches you want to collaborate on.
- You can also do `git push origin serverfix:serverfix`, which does the same thing — it says, “Take my serverfix and make it the remote’s serverfix.” You can use this format to push a local branch into a remote branch that is named differently.
- If you already have a local branch and want to set it to a remote branch you just pulled down, or want to change the upstream branch you’re tracking, you can use the `-u` or `--set-upstream-to` option to `git branch` to explicitly set it at any time.
- If you want to see what tracking branches you have set up, you can use the `-vv` option to `git branch`.

## When NOT to use

- That way, you can use private branches for work you don’t want to share, and push up only the topic branches you want to collaborate on.
- For working with remotes, use the `git-working-with-remotes` skill instead.
- For the refspec, use the `git-the-refspec` skill instead.
- For branch management, use the `git-branch-management` skill instead.

## Key concepts

- Remote-tracking branches are references to the state of remote branches.
- Because that server has a subset of the data your `origin` server has right now, Git fetches no data but sets a remote-tracking branch called `teamone/master` to point to the commit that `teamone` has as its `master` branch.
- You can also do `git push origin serverfix:serverfix`, which does the same thing — it says, “Take my serverfix and make it the remote’s serverfix.” You can use this format to push a local branch into a remote branch that is named differently.
- If you’re on a tracking branch and type `git pull`, Git automatically knows which server to fetch from and which branch to merge in.
- However, you can set up other tracking branches if you wish — ones that track branches on other remotes, or don’t track the `master` branch.
- The simple case is the example you just saw, running `git checkout -b <branch> <remote>/<branch>`.
- If you have a tracking branch set up as demonstrated in the last section, either by explicitly setting it or by having it created for you by the `clone` or `checkout` commands, `git pull` will look up what server and branch your current branch is tracking, fetch from that server and then try to merge in that remote branch.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git push origin --delete serverfix`
- **Note (from source):** Don’t type your password every time If you’re using an HTTPS URL to push over, the Git server will ask you for your username and password for authentication. By default it will prompt you on the terminal for this information so the server can tell if you’re allowed to push.

## Procedures

### Pushing

**Goal:** When you want to share a branch with the world, you need to push it up to a remote to which you have write access.

**Steps:**

1. Run `git push <remote> <branch>`:
   ```bash
   git push origin serverfix
   ```
   Expected output (excerpt):
   ```text
   Counting objects: 24, done.
   Delta compression using up to 8 threads.
   Compressing objects: 100% (15/15), done.
   Writing objects: 100% (24/24), 1.91 KiB | 0 bytes/s, done.
   ```
2. The next time one of your collaborators fetches from the server, they will get a reference to where the server’s version of `serverfix` is under the remote branch `origin/serverfix`:
   ```bash
   git fetch origin
   ```
   Expected output (excerpt):
   ```text
   remote: Counting objects: 7, done.
   remote: Compressing objects: 100% (2/2), done.
   remote: Total 3 (delta 0), reused 3 (delta 0)
   Unpacking objects: 100% (3/3), done.
   ```
3. If you want your own `serverfix` branch that you can work on, you can base it off your remote-tracking branch:
   ```bash
   git checkout -b serverfix origin/serverfix
   ```
   Expected output (excerpt):
   ```text
   Branch serverfix set up to track remote branch serverfix from origin.
   Switched to a new branch 'serverfix'
   ```

### Tracking Branches

**Goal:** Checking out a local branch from a remote-tracking branch automatically creates what is called a “tracking branch” (and the branch it tracks is called an “upstream branch”).

**Steps:**

1. This is a common enough operation that Git provides the `--track` shorthand:
   ```bash
   git checkout --track origin/serverfix
   ```
   Expected output (excerpt):
   ```text
   Branch serverfix set up to track remote branch serverfix from origin.
   Switched to a new branch 'serverfix'
   ```
2. If the branch name you’re trying to checkout (a) doesn’t exist and (b) exactly matches a name on only one remote, Git will create a tracking branch for you:
   ```bash
   git checkout serverfix
   ```
   Expected output (excerpt):
   ```text
   Branch serverfix set up to track remote branch serverfix from origin.
   Switched to a new branch 'serverfix'
   ```
3. To set up a local branch with a different name than the remote branch, you can easily use the first version with a different local branch name:
   ```bash
   git checkout -b sf origin/serverfix
   ```
   Expected output (excerpt):
   ```text
   Branch sf set up to track remote branch serverfix from origin.
   Switched to a new branch 'sf'
   ```
4. If you already have a local branch and want to set it to a remote branch you just pulled down, or want to change the upstream branch you’re tracking, you can use the `-u` or `--set-upstream-to` option to `git branch` to explicitly set it at any time.
   ```bash
   git branch -u origin/serverfix
   ```
   Expected output (excerpt):
   ```text
   Branch serverfix set up to track remote branch serverfix from origin.
   ```
5. This will list out your local branches with more information including what each branch is tracking and if your local branch is ahead, behind or both.
   ```bash
   git branch -vv
   ```
   Expected output (excerpt):
   ```text
     iss53     7e424c3 [origin/iss53: ahead 2] Add forgotten brackets
     master    1ae2a45 [origin/master] Deploy index fix
   * serverfix f8674d9 [teamone/server-fix-good: ahead 3, behind 1] This should do it
     testing   5ea463a Try something new
   ```
6. You could do that like this:
   ```bash
   git fetch --all; git branch -vv
   ```

**Verify:** run `git branch -vv` - expect something like:
```text
  iss53     7e424c3 [origin/iss53: ahead 2] Add forgotten brackets
  master    1ae2a45 [origin/master] Deploy index fix
* serverfix f8674d9 [teamone/server-fix-good: ahead 3, behind 1] This should do it
  testing   5ea463a Try something new
```

**If it fails:** Next we can see that our `serverfix` branch is tracking the `server-fix-good` branch on our `teamone` server and is ahead by three and behind by one, meaning that there is one commit on the server we haven’t merged in yet and three commits locally that we haven’t pushed.

### Deleting Remote Branches

**Goal:** You can delete a remote branch using the `--delete` option to `git push`.

**Steps:**

1. If you want to delete your `serverfix` branch from the server, you run the following:
   ```bash
   git push origin --delete serverfix
   ```
   Expected output (excerpt):
   ```text
   To https://github.com/schacon/simplegit
    - [deleted]         serverfix
   ```

**If it fails:** The Git server will generally keep the data there for a while until a garbage collection runs, so if it was accidentally deleted, it’s often easy to recover.

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git checkout -b` | The simple case is the example you just saw, running `git checkout -b <branch> <remote>/<branch>`. | `git checkout -b sf origin/serverfix` |
| `git push` | You can also do `git push origin serverfix:serverfix`, which does the same thing — it says, “Take my serverfix and make it the remote’s serverfix.” You can use this format to push a local branch into a remote branch that is named differently. | `git push origin serverfix` |
| `git fetch` | However, there is a command called `git pull` which is essentially a `git fetch` immediately followed by a `git merge` in most cases. | `git fetch origin` |
| `git checkout --track` | This is a common enough operation that Git provides the `--track` shorthand | `git checkout --track origin/serverfix` |
| `git checkout` | The simple case is the example you just saw, running `git checkout -b <branch> <remote>/<branch>`. | `git checkout serverfix` |
| `git branch -u` | If you already have a local branch and want to set it to a remote branch you just pulled down, or want to change the upstream branch you’re tracking, you can use the `-u` or `--set-upstream-to` option to `git branch` to explicitly set it at any time. | `git branch -u origin/serverfix` |
| `git branch -vv` | This will list out your local branches with more information including what each branch is tracking and if your local branch is ahead, behind or both. | `git branch -vv` |
| `git fetch -vv` | You could do that like this | `git fetch --all; git branch -vv` |
| `git push --delete` | If you want to delete your `serverfix` branch from the server, you run the following | `git push origin --delete serverfix` |

## Decision guide

- If you didn’t want it to be called `serverfix` on the remote, you could instead run `git push originserverfix:awesomebranch` to push your local `serverfix` branch to the `awesomebranch` branch on the remote project.

## Troubleshooting

- **Note:** “origin” is not special Just like the branch name “master” does not have any special meaning in Git, neither does “origin”. While “master” is the default name for a starting branch when you run `git init` which is the only reason it’s widely used, “origin” is the default name for a remote when you run `git clone`. If you run `git clone -o booyah` instead, then you will have `booyah/master` as your default remote branch.
- **Note:** Upstream shorthand When you have a tracking branch set up, you can reference its upstream branch with the `@{upstream}` or `@{u}` shorthand. So if you’re on the `master` branch and it’s tracking `origin/master`, you can say something like `git merge @{u}` instead of `gitmerge origin/master` if you wish.

## Related skills

- `git-working-with-remotes` - Working with Remotes
- `git-the-refspec` - The Refspec
- `git-branch-management` - Branch Management
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project

## Source

"Pro Git", pages 91-101. Sections: Remote Branches; Remote Branches > Pushing; Remote Branches > Tracking Branches; Remote Branches > Pulling; Remote Branches > Deleting Remote Branches.
