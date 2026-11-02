---
name: git-recording-changes-to-the-repository
description: "Recording Changes to the Repository playbook extracted from \"Pro Git\". The CONTRIBUTING.md file appears under a section named “Changes not staged for commit” — which means that a file that is tracked has been modified in the working directory but not yet staged. Use when the user asks about recording changes to the repository, git add, git status, git diff, command, staged, git commit; or mentions git status, git add, git rm, echo, git diff, git mv."
---

# Recording Changes to the Repository

The `CONTRIBUTING.md` file appears under a section named “Changes not staged for commit” — which means that a file that is tracked has been modified in the working directory but not yet staged.

_Built from "Pro Git" (pages 34-46) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **recording changes to the repository** (git add, git status, git diff, command, staged).
- The user wants to run or understand `git status`.
- The user wants to run or understand `git add`.
- The user wants to run or understand `git rm`.
- The user wants to run or understand `echo`.
- If the `git status` command is too vague for you — you want to know exactly what you changed, not just which files were changed — you can use the `git diff` command.
- For another example, if you stage the `CONTRIBUTING.md` file and then edit it, you can use `git diff` to see the changes in the file that are staged and the changes that are unstaged.

## When NOT to use

- For undoing things, use the `git-undoing-things` skill instead.
- For interactive staging, use the `git-interactive-staging` skill instead.
- For basic snapshotting, use the `git-basic-snapshotting` skill instead.

## Key concepts

- As you edit files, Git sees them as modified, because you’ve changed them since your last commit.
- As you work, you selectively stage these modified files and then commit all those staged changes, and the cycle repeats.
- If the `git status` command is too vague for you — you want to know exactly what you changed, not just which files were changed — you can use the `git diff` command.
- If you’ve staged all of your changes, `git diff` will give you no output.
- For another example, if you stage the `CONTRIBUTING.md` file and then edit it, you can use `git diff` to see the changes in the file that are staged and the changes that are unstaged.
- In this case, let’s say that the last time you ran `git status`, you saw that everything was staged, so you’re ready to commit your changes.
- You can see that the commit has given you some output about itself: which branch you committed to (`master`), what SHA-1 checksum the commit has (`463dc4f`), how many files were changed, and statistics about lines added and removed in the commit.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- This is convenient, but be careful; sometimes this flag will cause you to include unwanted changes.
- If you modified the file or had already added it to the staging area, you must force the removal with the `-f` option.

## Procedures

### Checking the Status of Your Files

**Goal:** Checking the Status of Your Files

**Steps:**

1. If you run this command directly after a clone, you should see something like this:
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   nothing to commit, working tree clean
   ```
2. If the file didn’t exist before, and you run `git status`, you see your untracked file like so:
   ```bash
   echo 'My Project' > README
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Untracked files:
     (use "git add <file>..." to include in what will be committed)
   ```

### Tracking New Files

**Goal:** You can tell that it’s staged because it’s under the “Changes to be committed” heading.

**Steps:**

1. To begin tracking the `README` file, you can run this:
   ```bash
   git add README
   ```
2. If you run your status command again, you can see that your `README` file is now tracked and staged to be committed:
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
   ```
3. Run:
   ```text
     (use "git restore --staged <file>..." to unstage)
       new file:   README
   ```

**Verify:** run `git status` - expect something like:
```text
On branch master
Your branch is up-to-date with 'origin/master'.
Changes to be committed:
```

### Staging Modified Files

**Goal:** The `CONTRIBUTING.md` file appears under a section named “Changes not staged for commit” — which means that a file that is tracked has been modified in the working directory but not yet staged.

**Steps:**

1. If you change a previously tracked file called `CONTRIBUTING.md` and then run your `git status` command again, you get something that looks like this:
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
   ```
2. Let’s run `git add` now to stage the `CONTRIBUTING.md` file, and then run `git status` again:
   ```bash
   git add CONTRIBUTING.md
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
   ```
3. Run:
   ```text
       modified:   CONTRIBUTING.md
   ```
4. However, let’s run `git status` one more time:
   ```bash
   vim CONTRIBUTING.md
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
   ```
5. If you modify a file after you run `git add`, you have to run `git add` again to stage the latest version of the file:
   ```bash
   git add CONTRIBUTING.md
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
   ```

**If it fails:** `git add` is a multipurpose command — you use it to begin tracking new files, to stage files, and to do other things like marking merge-conflicted files as resolved.

### Viewing Your Staged and Unstaged Changes

**Goal:** If the `git status` command is too vague for you — you want to know exactly what you changed, not just which files were changed — you can use the `git diff` command.

**Steps:**

1. If you run your `git status` command, you once again see something like this:
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   ```
2. Run:
   ```text
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
       modified:   README
   Changes not staged for commit:
     (use "git add <file>..." to update what will be committed)
     (use "git checkout -- <file>..." to discard changes in working directory)
       modified:   CONTRIBUTING.md
   ```
3. To see what you’ve changed but not yet staged, type `git diff` with no other arguments:
   ```bash
   git diff
   ```
   Expected output (excerpt):
   ```text
   diff --git a/CONTRIBUTING.md b/CONTRIBUTING.md
   index 8ebb991..643e24f 100644
   --- a/CONTRIBUTING.md
   +++ b/CONTRIBUTING.md
   ```
4. This command compares your staged changes to your last commit:
   ```bash
   git diff --staged
   ```
   Expected output (excerpt):
   ```text
   diff --git a/README b/README
   new file mode 100644
   index 0000000..03902a1
   --- /dev/null
   ```
5. If our environment looks like this:
   ```bash
   git add CONTRIBUTING.md
   echo '# test line' >> CONTRIBUTING.md
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
   ```
6. Now you can use `git diff` to see what is still unstaged:
   ```bash
   git diff
   ```
   Expected output (excerpt):
   ```text
   diff --git a/CONTRIBUTING.md b/CONTRIBUTING.md
   index 643e24f..87f08c8 100644
   --- a/CONTRIBUTING.md
   +++ b/CONTRIBUTING.md
   ```

_2 more step(s) in references/procedures.md._

**Verify:** run `git diff --cached` - expect something like:
```text
diff --git a/CONTRIBUTING.md b/CONTRIBUTING.md
index 8ebb991..643e24f 100644
--- a/CONTRIBUTING.md
+++ b/CONTRIBUTING.md
@@ -65,7 +65,8 @@ branch directly, things can get messy.
 Please include a nice description of your changes when you submit your PR;
```

### Committing Your Changes

**Goal:** In this case, let’s say that the last time you ran `git status`, you saw that everything was staged, so you’re ready to commit your changes.

**Steps:**

1. The simplest way to commit is to type `git commit`:
   ```bash
   git commit
   ```
2. The editor displays the following text (this example is a Vim screen):
   ```text
   # Please enter the commit message for your changes. Lines starting
   # with '#' will be ignored, and an empty message aborts the commit.
   # On branch master
   # Your branch is up-to-date with 'origin/master'.
   #
   # Changes to be committed:
   #   new file:   README
   #   modified:   CONTRIBUTING.md
   #
   ~
   ~
   ~
   ".git/COMMIT_EDITMSG" 9L, 283C
   ```
3. Alternatively, you can type your commit message inline with the `commit` command by specifying it after a `-m` flag, like this:
   ```bash
   git commit -m "Story 182: fix benchmarks for speed"
   ```
   Expected output (excerpt):
   ```text
   [master 463dc4f] Story 182: fix benchmarks for speed
    2 files changed, 2 insertions(+)
    create mode 100644 README
   ```

**If it fails:** Every time you perform a commit, you’re recording a snapshot of your project that you can revert to or compare to later.

More procedures in [references/procedures.md](references/procedures.md):

- Short Status
- Ignoring Files
- Viewing Your Staged and Unstaged Changes
- Skipping the Staging Area
- Removing Files
- Moving Files

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git status` | The main tool you use to determine which files are in which state is the `git status` command. | `git status` |
| `git add` | `git add` is a multipurpose command — you use it to begin tracking new files, to stage files, and to do other things like marking merge-conflicted files as resolved. | `git add README` |
| `git rm` | Then, if you run `git rm`, it stages the file’s removal | `git rm \*~` |
| `git diff` | Now you can use `git diff` to see what is still unstaged | `git diff` |
| `git mv` | The only real difference is that `git mv` is one command instead of three — it’s a convenience function. | `git mv README.md README` |
| `git status -s` | If you run `git status -s` or `gitstatus --short` you get a far more simplified output from the command | `git status -s` |
| `git diff --staged` | This command compares your staged changes to your last commit | `git diff --staged` |
| `git diff --cached` | and `git diff --cached` to see what you’ve staged so far (`--staged` and `--cached` are synonyms) | `git diff --cached` |
| `git commit` | The simplest way to commit is to type `git commit` | `git commit` |
| `git commit -m` | Alternatively, you can type your commit message inline with the `commit` command by specifying it after a `-m` flag, like this | `git commit -m "Story 182: fix benchmarks for speed"` |
| `git commit -a -m` | Git automatically stage every file that is already tracked before doing the commit, letting you skip the `git add` part | `git commit -a -m 'Add new benchmarks'` |
| `git rm --cached` | To do this, use the `--cached` option | `git rm --cached README` |

## Decision guide

- The only real difference is that `git mv` is one command instead of three — it’s a convenience function.

## Troubleshooting

- **Note:** GitHub changed the default branch name from `master` to `main` in mid-2020, and other Git hosts followed suit. So you may find that the default branch name in some newly created repositories is `main` and not `master`. In addition, the default branch name can be changed (as you have seen in Your default branch name), so you may see a different name for the default branch.
- **Tip:** GitHub maintains a fairly comprehensive list of good `.gitignore` file examples for dozens of projects and languages at https://github.com/github/gitignore if you want a starting point for your project. In the simple case, a repository might have a single `.gitignore` file in its root directory, which applies recursively to the entire repository. However, it is also possible to have additional `.gitignore` files in subdirectories. The rules in these nested `.gitignore` files apply only to the files under the directory where they are located. The Linux kernel source repository has 206 `.gitignore` files.
- **Note:** Git Diff in an External Tool We will continue to use the `git diff` command in various ways throughout the rest of the book. There is another way to look at these diffs if you prefer a graphical or external diff viewing program instead. If you run `git difftool` instead of `git diff`, you can view any of these diffs in software like emerge, vimdiff and many more (including commercial products). Run `git difftool --tool-help` to see what is available on your system.
- **Note:** This is set by your shell’s `EDITOR` environment variable — usually vim or emacs, although you can configure it with whatever you want using the `git config--global core.editor` command as you saw in Getting Started.
- **Note:** For an even more explicit reminder of what you’ve modified, you can pass the `-v` option to `git commit`. Doing so also puts the diff of your change in the editor so you can see exactly what changes you’re committing.

## Related skills

- `git-undoing-things` - Undoing Things
- `git-interactive-staging` - Interactive Staging
- `git-basic-snapshotting` - Basic Snapshotting
- `git-stashing-and-cleaning` - Stashing and Cleaning

## Source

"Pro Git", pages 34-46. Sections: Recording Changes to the Repository; Recording Changes to the Repository > Checking the Status of Your Files; Recording Changes to the Repository > Tracking New Files; Recording Changes to the Repository > Staging Modified Files; Recording Changes to the Repository > Short Status; Recording Changes to the Repository > Ignoring Files; Recording Changes to the Repository > Viewing Your Staged and Unstaged Changes; Recording Changes to the Repository > Committing Your Changes; Recording Changes to the Repository > Skipping the Staging Area; Recording Changes to the Repository > Removing Files; Recording Changes to the Repository > Moving Files.
