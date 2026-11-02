---
name: git-replace
description: "Replace playbook extracted from \"Pro Git\". The replace command lets you specify an object in Git and say \"every time you refer to this object, pretend it’s a different object\". Use when the user asks about replace, base commit, recent history, commit object, entire history, object database, git replace; or mentions git replace, git log --oneline, git log --oneline --decorate, git remote, git branch, git push."
---

# Replace

The `replace` command lets you specify an object in Git and say "every time you refer to this object, pretend it’s a different object".

_Built from "Pro Git" (pages 328-336) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **replace** (base commit, recent history, commit object, entire history, object database).
- The user wants to run or understand `git replace`.
- The user wants to run or understand `git log --oneline`.
- The user wants to run or understand `git log --oneline --decorate`.
- The user wants to run or understand `git remote`.
- The `replace` command lets you specify an object in Git and say "every time you refer to this object, pretend it’s a different object".

## When NOT to use

- For branches in a nutshell, use the `git-branches-in-a-nutshell` skill instead.
- For git as a client, use the `git-as-a-client` skill instead.
- For git references, use the `git-references` skill instead.

## Key concepts

- This is most commonly useful for replacing one commit in your history with another one without having to rebuild the entire history with, say, `git filter-branch`.
- You can graft one history onto the other by "replacing" the earliest commit in the new line with the latest commit on the older one.
- The second line will just be commits four and five - that will be the recent history.
- We need an overlap so we can replace a commit in one with an equivalent commit in the other, so we’re going to truncate this to just commits four and five (so commit four overlaps).
- We can push that new history to a new project and now when people clone that repository, they will only see the most recent two commits and then a base commit with instructions.
- To combine them, you can simply call `git replace` with the commit you want to replace and then the commit you want to replace it with.
- Without having to change all the SHA-1s upstream, we were able to replace one commit in our history with an entirely different commit and all the normal tools (`bisect`, `blame`, etc) will work how we would expect them to.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git rebase --onto 622e88 9c68fdc`

## Procedures

### Replace

**Goal:** The `replace` command lets you specify an object in Git and say "every time you refer to this object, pretend it’s a different object".

**Steps:**

1. We’ll use a simple repository with five simple commits:
   ```bash
   git log --oneline
   ```
   Expected output (excerpt):
   ```text
   ef989d8 Fifth commit
   c6e1e95 Fourth commit
   9c68fdc Third commit
   945704c Second commit
   ```
2. Well, creating the historical history is easy, we can just put a branch in the history and then push that branch to the `master` branch of a new remote repository.
   ```bash
   git branch history c6e1e95
   git log --oneline --decorate
   ```
   Expected output (excerpt):
   ```text
   ef989d8 (HEAD, master) Fifth commit
   c6e1e95 (history) Fourth commit
   9c68fdc Third commit
   945704c Second commit
   ```
3. Now we can push the new `history` branch to the `master` branch of our new repository:
   ```bash
   git remote add project-history https://github.com/schacon/project-history
   git push project-history history:master
   ```
   Expected output (excerpt):
   ```text
   Counting objects: 12, done.
   Delta compression using up to 2 threads.
   Compressing objects: 100% (4/4), done.
   Writing objects: 100% (12/12), 907 bytes, done.
   ```
4. We need an overlap so we can replace a commit in one with an equivalent commit in the other, so we’re going to truncate this to just commits four and five (so commit four overlaps).
   ```bash
   git log --oneline --decorate
   ```
   Expected output (excerpt):
   ```text
   ef989d8 (HEAD, master) Fifth commit
   c6e1e95 (history) Fourth commit
   9c68fdc Third commit
   945704c Second commit
   ```
5. We can create our base commit using the `commit-tree` command, which just takes a tree and will give us a brand new, parentless commit object SHA-1 back.
   ```bash
   echo 'Get history from blah blah blah' | git commit-tree 9c68fdc^{tree}
   ```
   Expected output (excerpt):
   ```text
   622e88e9cbfbacfb75b5279245b9fb38dfea10cf
   ```
6. The `--onto` argument will be the SHA-1 we just got back from `commit-tree` and the rebase point will be the third commit (the parent of the first commit we want to keep, `9c68fdc`):
   ```bash
   git rebase --onto 622e88 9c68fdc
   ```
   Expected output (excerpt):
   ```text
   First, rewinding head to replay your work on top of it...
   Applying: fourth commit
   Applying: fifth commit
   ```

_8 more step(s) in references/procedures.md._

**Verify:** run `git cat-file -p 81a708d` - expect something like:
```text
tree 7bc544cf438903b65ca9104a1e30345eee6c083d
parent 9c68fdceee073230f19ebb8b5e7fc71b479c0252
author Scott Chacon <schacon@gmail.com> 1268712581 -0700
committer Scott Chacon <schacon@gmail.com> 1268712581 -0700
fourth commit
```

More procedures in [references/procedures.md](references/procedures.md):

- Replace

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git log --oneline` | We’ll use a simple repository with five simple commits | `git log --oneline` |
| `git log --oneline --decorate` | Well, creating the historical history is easy, we can just put a branch in the history and then push that branch to the `master` branch of a new remote repository. | `git log --oneline --decorate` |
| `git remote` | Now we can push the new `history` branch to the `master` branch of our new repository | `git remote add project-history https://github.com/schacon/project-history` |
| `git branch` | Well, creating the historical history is easy, we can just put a branch in the history and then push that branch to the `master` branch of a new remote repository. | `git branch history c6e1e95` |
| `git push` | Now we can push the new `history` branch to the `master` branch of our new repository | `git push project-history history:master` |
| `git rebase --onto` | OK, so now that we have a base commit, we can rebase the rest of our history on top of that with `git rebase --onto`. | `git rebase --onto 622e88 9c68fdc` |
| `git clone` | To get the history data after cloning this truncated repository, one would have to add a second remote for the historical repository and fetch | `git clone https://github.com/schacon/project` |
| `git fetch` | To get the history data after cloning this truncated repository, one would have to add a second remote for the historical repository and fetch | `git fetch project-history` |
| `git replace` | To combine them, you can simply call `git replace` with the commit you want to replace and then the commit you want to replace it with. | `git replace 81a708d c6e1e95` |
| `git cat-file -p` | Even if you run a command like `cat-file`, it will show you the replaced data | `git cat-file -p 81a708d` |
| `git for-each-ref` | Another interesting thing is that this data is kept in our references | `git for-each-ref` |

## Troubleshooting

- **Note:** The `commit-tree` command is one of a set of commands that are commonly referred to as 'plumbing' commands. These are commands that are not generally meant to be used directly, but instead are used by other Git commands to do smaller jobs. On occasions when we’re doing weirder things like this, they allow us to do really low-level things but are not meant for daily use. You can read more about plumbing commands in Plumbing and Porcelain.

## Related skills

- `git-branches-in-a-nutshell` - Branches in a Nutshell
- `git-as-a-client` - Git as a Client
- `git-references` - Git References
- `git-objects` - Git Objects

## Source

"Pro Git", pages 328-336. Sections: Replace.
