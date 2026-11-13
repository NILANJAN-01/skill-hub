---
name: git-rebasing
description: "Rebase a branch (git rebase, --onto), rebase vs merge, fix pushed rebases. Use when handling rebasing or a linear history."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Rebasing"
  category: git-branching
  source: "Pro Git, 2nd edition"
  pages: "101-110"
---

# Rebasing

In Git, there are two main ways to integrate changes from one branch into another: the `merge` and the `rebase`.

_Built from "Pro Git" (pages 101-110) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **rebasing** (commit history, rebase commits, git rebase, git pull, merge commit).
- The user wants to run or understand `git rebase`.
- The user wants to run or understand `git rebase --onto`.
- The user wants to run or understand `git checkout`.
- The user wants to run or understand `git merge`.

## When NOT to use

- Do not rebase commits that exist outside your repository and that people may have based work on.
- If you only ever rebase commits that have never left your own computer, you’ll be just fine.
- You can get the best of both worlds: rebase local changes before pushing to clean up your work, but never rebase anything that you’ve pushed somewhere.
- For rewriting history, use the `git-rewriting-history` skill instead.
- For contributing to a project, use the `git-distributed-git-contributing-to-a-project` skill instead.
- For maintaining a project, use the `git-distributed-git-maintaining-a-project` skill instead.

## Key concepts

- This operation works by going to the common ancestor of the two branches (the one you’re on and the one you’re rebasing onto), getting the diff introduced by each commit of the branch you’re on, saving those diffs to temporary files, resetting the current branch to the same commit as the branch you are rebasing onto, and finally applying each change in turn.
- Note that the snapshot pointed to by the final commit you end up with, whether it’s the last of the rebased commits for a rebase or the final merge commit after a merge, is the same snapshot — it’s only the history that is different.
- If you push commits somewhere and others pull them down and base work on them, and then you rewrite those commits with `git rebase` and push them up again, your collaborators will have to re-merge their work and things will get messy when you try to pull their work back into yours.
- If you pull down work that was rewritten and rebase it on top of the new commits from your partner, Git can often successfully figure out what is uniquely yours and apply them back on top of the new branch.
- If you rebase commits that have been pushed, but that no one else has based commits from, you’ll also be fine.
- People in this camp use tools like `rebase` and `filter-branch` to rewrite their commits before they’re merged into the mainline branch.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git rebase master`
  - `git rebase --onto master server client`
  - `git rebase master server`
- If someone on your team force pushes changes that overwrite work that you’ve based work on, your challenge is to figure out what is yours and what they’ve rewritten.

## Procedures

### The Basic Rebase

**Goal:** This operation works by going to the common ancestor of the two branches (the one you’re on and the one you’re rebasing onto), getting the diff introduced by each commit of the branch you’re on, saving those diffs to temporary files, resetting the current branch to the same commit as the branch you are rebasing onto, and finally applying each change in turn.

**Steps:**

1. For this example, you would check out the `experiment` branch, and then rebase it onto the `master` branch as follows:
   ```bash
   git checkout experiment
   git rebase master
   ```
   Expected output (excerpt):
   ```text
   First, rewinding head to replay your work on top of it...
   Applying: added staged command
   ```
2. At this point, you can go back to the `master` branch and do a fast-forward merge.
   ```bash
   git checkout master
   git merge experiment
   ```

### More Interesting Rebases

**Goal:** You can also have your rebase replay on something other than the rebase target branch.

**Steps:**

1. You can take the changes on `client` that aren’t on `server` (`C8` and `C9`) and replay them on your `master` branch by using the `--onto` option of `git rebase`:
   ```bash
   git rebase --onto master server client
   ```
2. Now you can fast-forward your `master` branch (see Fast-forwarding your `master` branch to include the `client` branch changes):
   ```bash
   git checkout master
   git merge client
   ```
3. You can rebase the `server` branch onto the `master` branch without having to check it out first by running `git rebase <basebranch><topicbranch>` — which checks out the topic branch (in this case, `server`) for you and replays it onto the base branch (`master`):
   ```bash
   git rebase master server
   ```
4. Then, you can fast-forward the base branch (`master`):
   ```bash
   git checkout master
   git merge server
   ```
5. You can remove the `client` and `server` branches because all the work is integrated and you don’t need them anymore, leaving your history for this entire process looking like Final commit history:
   ```bash
   git branch -d client
   git branch -d server
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git checkout` | For this example, you would check out the `experiment` branch, and then rebase it onto the `master` branch as follows | `git checkout master` |
| `git merge` | At this point, you can go back to the `master` branch and do a fast-forward merge. | `git merge client` |
| `git rebase` | Or you could do it manually with a `git fetch` followed by a `git rebase teamone/master` in this case. | `git rebase master` |
| `git branch -d` | You can remove the `client` and `server` branches because all the work is integrated and you don’t need them anymore, leaving your history for this entire process looking like Final commit history | `git branch -d client` |
| `git rebase --onto` | You can take the changes on `client` that aren’t on `server` (`C8` and `C9`) and replay them on your `master` branch by using the `--onto` option of `git rebase` | `git rebase --onto master server client` |

## Decision guide

- If you follow that guideline, you’ll be fine.
- You can also simplify this by running a `git pull --rebase` instead of a normal `git pull`.
- If you rebase commits that have been pushed, but that no one else has based commits from, you’ll also be fine.
- If you or a partner does find it necessary at some point, make sure everyone knows to run `git pull--rebase` to try to make the pain after it happens a little bit simpler.

## Related skills

- `git-rewriting-history` - Rewriting History
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-advanced-merging` - Advanced Merging

## Source

"Pro Git", pages 101-110. Sections: Rebasing; Rebasing > The Basic Rebase; Rebasing > More Interesting Rebases; Rebasing > The Perils of Rebasing; Rebasing > Rebase When You Rebase; Rebasing > Rebase vs. Merge.
