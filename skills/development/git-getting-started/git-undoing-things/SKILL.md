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

_Built from "Pro Git" (pages 52-56) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **undoing things** (git restore, git reset, previous commit, undo, commit message).
- The user wants to run or understand `git status`.
- The user wants to run or understand `git add`.
- The user wants to run or understand `git commit --amend`.
- The user wants to run or understand `git commit -m`.

## When NOT to use

- For recording changes to the repository, use the `git-recording-changes-to-the-repository` skill instead.
- For reset demystified, use the `git-reset-demystified` skill instead.
- For interactive staging, use the `git-interactive-staging` skill instead.

## Key concepts

- This command takes your staging area and uses it for the commit.
- If you’ve made no changes since your last commit (for instance, you run this command immediately after your previous commit), then your snapshot will look exactly the same, and all you’ll change is your commit message.
- The nice part is that the command you use to determine the state of those two areas also reminds you how to undo changes to them.
- Right below the “Changes to be committed” text, it says use `git reset HEAD <file>…` to unstage.
- From Git version 2.23.0 onwards, Git will use `git restore` instead of `gitreset` for many undo operations.
- The next two sections demonstrate how to work with your staging area and working directory changes with `git restore`.
- Right below the “Changes to be committed” text, it says use `git restore --staged <file>…` to unstage.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git commit --amend`
  - `git checkout -- CONTRIBUTING.md`
  - `git restore CONTRIBUTING.md`
- **Note (from source):** It’s important to understand that when you’re amending your last commit, you’re not so much fixing it as replacing it entirely with a new, improved commit that pushes the old commit out of the way and puts the new commit in its place. Effectively, it’s as if the previous commit never happened, and it won’t show up in your repository history.
- **Note (from source):** Only amend commits that are still local and have not been pushed somewhere. Amending previously pushed commits and force pushing the branch will cause problems for your collaborators. For more on what happens when you do this and how to recover if you’re on the receiving end read The Perils of Rebasing.
- **Note (from source):** It’s true that `git reset` can be a dangerous command, especially if you provide the `--hard` flag. However, in the scenario described above, the file in your working directory is not touched, so it’s relatively safe.
- **Important (from source):** It’s important to understand that `git checkout -- <file>` is a dangerous command. Any local changes you made to that file are gone — Git just replaced that file with the last staged or committed version. Don’t ever use this command unless you
- **Important (from source):** It’s important to understand that `git restore <file>` is a dangerous command. Any local changes you made to that file are gone — Git just replaced that file with the last staged or committed version. Don’t ever use this command unless you absolutely know that you don’t want those unsaved local changes.
- Be careful, because you can’t always undo some of these undos.
- This is one of the few areas in Git where you may lose some work if you do it wrong.
- You can edit the message the same as always, but it overwrites your previous commit.
- It tells you pretty explicitly how to discard the changes you’ve made.
- Even commits that were on branches that were deleted or commits that were overwritten with an `--amend` commit can be recovered (see Data Recovery for data recovery).
- However, anything you lose that was never committed is likely never to be seen again.

## Procedures

### Undoing Things

**Goal:** At any stage, you may want to undo something.

**Steps:**

1. If you want to redo that commit, make the additional changes you forgot, stage them, and commit again using the `--amend` option:
   ```bash
   git commit --amend
   ```
2. As an example, if you commit and then realize you forgot to stage the changes in a file you wanted to add to this commit, you can do something like this:
   ```bash
   git commit -m 'Initial commit'
   git add forgotten_file
   ```
3. Run:
   ```bash
   git commit --amend
   ```

**If it fails:** At any stage, you may want to undo something.

### Unstaging a Staged File

**Goal:** The nice part is that the command you use to determine the state of those two areas also reminds you how to undo changes to them.

**Steps:**

1. The `git status` command reminds you:
   ```bash
   git add *
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
       renamed:    README.md -> README
   ```
2. So, let’s use that advice to unstage the `CONTRIBUTING.md` file:
   ```bash
   git reset HEAD CONTRIBUTING.md
   git status
   ```
   Expected output (excerpt):
   ```text
   Unstaged changes after reset:
   M   CONTRIBUTING.md
   On branch master
   Changes to be committed:
   ```
3. Run:
   ```text
       renamed:    README.md -> README
   Changes not staged for commit:
     (use "git add <file>..." to update what will be committed)
     (use "git checkout -- <file>..." to discard changes in working directory)
       modified:   CONTRIBUTING.md
   ```

**If it fails:** The nice part is that the command you use to determine the state of those two areas also reminds you how to undo changes to them.

### Unmodifying a Modified File

**Goal:** Unmodifying a Modified File

**Steps:**

1. In the last example output, the unstaged area looks like this:
   ```text
   Changes not staged for commit:
     (use "git add <file>..." to update what will be committed)
     (use "git checkout -- <file>..." to discard changes in working directory)
       modified:   CONTRIBUTING.md
   ```
2. Let’s do what it says:
   ```bash
   git checkout -- CONTRIBUTING.md
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
       renamed:    README.md -> README
   ```

**If it fails:** How can you easily unmodify it — revert it back to what it looked like when you last committed (or initially cloned, or however you got it into your working directory)?

### Undoing things with git restore

**Goal:** From Git version 2.23.0 onwards, Git will use `git restore` instead of `gitreset` for many undo operations.

**Steps:**

1. The `git status` command reminds you:
   ```bash
   git add *
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Changes to be committed:
     (use "git restore --staged <file>..." to unstage)
       modified:   CONTRIBUTING.md
   ```
2. So, let’s use that advice to unstage the `CONTRIBUTING.md` file:
   ```bash
   git restore --staged CONTRIBUTING.md
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Changes to be committed:
     (use "git restore --staged <file>..." to unstage)
       renamed:    README.md -> README
   ```
3. Run:
   ```text
       modified:   CONTRIBUTING.md
   ```
4. In the last example output, the unstaged area looks like this:
   ```text
   Changes not staged for commit:
     (use "git add <file>..." to update what will be committed)
     (use "git restore <file>..." to discard changes in working directory)
       modified:   CONTRIBUTING.md
   ```
5. Let’s do what it says:
   ```bash
   git restore CONTRIBUTING.md
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Changes to be committed:
     (use "git restore --staged <file>..." to unstage)
       renamed:    README.md -> README
   ```

**If it fails:** From Git version 2.23.0 onwards, Git will use `git restore` instead of `gitreset` for many undo operations.

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git status` | The `git status` command reminds you | `git status` |
| `git add` | For example, let’s say you’ve changed two files and want to commit them as two separate changes, but you accidentally type `git add *` and stage them both. | `git add *` |
| `git commit --amend` | If you want to redo that commit, make the additional changes you forgot, stage them, and commit again using the `--amend` option | `git commit --amend` |
| `git commit -m` | As an example, if you commit and then realize you forgot to stage the changes in a file you wanted to add to this commit, you can do something like this | `git commit -m 'Initial commit'` |
| `git reset` | It’s basically an alternative to `git reset` which we just covered. | `git reset HEAD CONTRIBUTING.md` |
| `git checkout` | Let’s do what it says | `git checkout -- CONTRIBUTING.md` |
| `git restore --staged` | Right below the “Changes to be committed” text, it says use `git restore --staged <file>…` to unstage. | `git restore --staged CONTRIBUTING.md` |
| `git restore` | Git version 2.23.0 introduced a new command: `git restore`. | `git restore CONTRIBUTING.md` |

## Decision guide

- From Git version 2.23.0 onwards, Git will use `git restore` instead of `gitreset` for many undo operations.

## Related skills

- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-reset-demystified` - Reset Demystified
- `git-interactive-staging` - Interactive Staging
- `git-rewriting-history` - Rewriting History

## Source

"Pro Git", pages 52-56. Sections: Undoing Things; Undoing Things > Unstaging a Staged File; Undoing Things > Unmodifying a Modified File; Undoing Things > Undoing things with git restore.
