---
name: git-branches-in-a-nutshell
description: "Branches in a Nutshell playbook extracted from \"Pro Git\". In Git, this is a pointer to the local branch you’re currently on. Use when the user asks about branches in a nutshell, git log, git stores, git repository, master, git checkout, git switch; or mentions git branch, git log --oneline --decorate, git checkout, vim, git commit -a -m, git add."
---

# Branches in a Nutshell

In Git, this is a pointer to the local branch you’re currently on.

_Built from "Pro Git" (pages 69-76) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **branches in a nutshell** (git log, git stores, git repository, master, git checkout).
- The user wants to run or understand `git branch`.
- The user wants to run or understand `git log --oneline --decorate`.
- The user wants to run or understand `git checkout`.
- The user wants to run or understand `vim`.

## When NOT to use

- For basic branching and merging, use the `git-basic-branching-and-merging` skill instead.
- For git references, use the `git-references` skill instead.
- For reset demystified, use the `git-reset-demystified` skill instead.

## Key concepts

- The `git branch` command only created a new branch — it didn’t switch to that branch.
- You can easily see this by running a simple `git log` command that shows you where the branch pointers are pointing.
- This moves `HEAD` to point to the `testing` branch.
- This is interesting, because now your `testing` branch has moved forward, but your `master` branch still points to the commit you were on when you ran `git checkout` to switch branches.
- In other words, by default, `git log` will only show commit history below the branch you’ve checked out.
- It moved the HEAD pointer back to point to the `master` branch, and it reverted the files in your working directory back to the snapshot that `master` points to.
- Because a branch in Git is actually a simple file that contains the 40 character SHA-1 checksum of the commit it points to, branches are cheap to create and destroy.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- Because a branch in Git is actually a simple file that contains the 40 character SHA-1 checksum of the commit it points to, branches are cheap to create and destroy.

## Procedures

### Branches in a Nutshell

**Goal:** To really understand the way Git does branching, we need to take a step back and examine how Git stores its data.

**Steps:**

1. Staging the files computes a checksum for each one (the SHA-1 hash we mentioned in What is Git?), stores that version of the file in the Git repository (Git refers to them as blobs), and adds that checksum to the staging area:
   ```bash
   git add README test.rb LICENSE
   git commit -m 'Initial commit'
   ```

### Creating a New Branch

**Goal:** In Git, this is a pointer to the local branch you’re currently on.

**Steps:**

1. You do this with the `gitbranch` command:
   ```bash
   git branch testing
   ```
2. This option is called `--decorate`.
   ```bash
   git log --oneline --decorate
   ```
   Expected output (excerpt):
   ```text
   f30ab (HEAD -> master, testing) Add feature #32 - ability to add new formats to the
   central interface
   34ac2 Fix bug #1328 - stack overflow under certain conditions
   98ca9 Initial commit
   ```

**Verify:** run `git log --oneline --decorate` - expect something like:
```text
f30ab (HEAD -> master, testing) Add feature #32 - ability to add new formats to the
central interface
34ac2 Fix bug #1328 - stack overflow under certain conditions
98ca9 Initial commit
```

### Switching Branches

**Goal:** In other words, by default, `git log` will only show commit history below the branch you’ve checked out.

**Steps:**

1. Let’s switch to the new `testing` branch:
   ```bash
   git checkout testing
   ```
2. Well, let’s do another commit:
   ```bash
   vim test.rb
   git commit -a -m 'Make a change'
   ```
3. Let’s switch back to the `master` branch:
   ```bash
   git checkout master
   ```
4. Let’s make a few changes and commit again:
   ```bash
   vim test.rb
   git commit -a -m 'Make other changes'
   ```
5. If you run `git log --oneline --decorate--graph --all` it will print out the history of your commits, showing where your branch pointers are and how your history has diverged.
   ```bash
   git log --oneline --decorate --graph --all
   ```
   Expected output (excerpt):
   ```text
   * c2b9e (HEAD, master) Make other changes
   | * 87ab2 (testing) Make a change
   |/
   * f30ab Add feature #32 - ability to add new formats to the central interface
   ```

**Verify:** run `git log --oneline --decorate --graph --all` - expect something like:
```text
* c2b9e (HEAD, master) Make other changes
| * 87ab2 (testing) Make a change
|/
* f30ab Add feature #32 - ability to add new formats to the central interface
* 34ac2 Fix bug #1328 - stack overflow under certain conditions
* 98ca9 Initial commit of my project
```

**If it fails:** It moved the HEAD pointer back to point to the `master` branch, and it reverted the files in your working directory back to the snapshot that `master` points to.

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git log --oneline --decorate` | If you run `git log --oneline --decorate--graph --all` it will print out the history of your commits, showing where your branch pointers are and how your history has diverged. | `git log --oneline --decorate` |
| `git checkout` | From Git version 2.23 onwards you can use `git switch` instead of `git checkout` to | `git checkout master` |
| `git commit -a -m` | Well, let’s do another commit | `git commit -a -m 'Make a change'` |
| `git add` | Staging the files computes a checksum for each one (the SHA-1 hash we mentioned in What is Git?), stores that version of the file in the Git repository (Git refers to them as blobs), and adds that checksum to the staging area | `git add README test.rb LICENSE` |
| `git commit -m` | Staging the files computes a checksum for each one (the SHA-1 hash we mentioned in What is Git?), stores that version of the file in the Git repository (Git refers to them as blobs), and adds that checksum to the staging area | `git commit -m 'Initial commit'` |
| `git branch` | The `git branch` command only created a new branch — it didn’t switch to that branch. | `git branch testing` |

## Troubleshooting

- **Note:** The “master” branch in Git is not a special branch. It is exactly like any other branch. The only reason nearly every repository has one is that the `git init` command creates it by default and most people don’t bother to change it.
- **Note:** `git log` doesn’t show all the branches all the time
- **Note:** Switching branches changes files in your working directory It’s important to note that when you switch branches in Git, files in your working directory will change. If you switch to an older branch, your working directory will be reverted to look like it did the last time you committed on that branch. If Git cannot do it cleanly, it will not let you switch at all.
- **Note:** Creating a new branch and switching to it at the same time It’s typical to create a new branch and want to switch to that new branch at the same time — this can be done in one operation with `git checkout -b<newbranchname>`.
- **Note:** •Switch to an existing branch: `git switch testing-branch`. •Create a new branch and switch to it: `git switch -c new-branch`. The `-c` flag

## Related skills

- `git-basic-branching-and-merging` - Basic Branching and Merging
- `git-references` - Git References
- `git-reset-demystified` - Reset Demystified
- `git-objects` - Git Objects

## Source

"Pro Git", pages 69-76. Sections: Branches in a Nutshell; Branches in a Nutshell > Creating a New Branch; Branches in a Nutshell > Switching Branches.
