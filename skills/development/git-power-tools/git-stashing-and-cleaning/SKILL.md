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

_Built from "Pro Git" (pages 236-242) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **stashing and cleaning** (git stash, working directory, git clean, remove, branch).
- The user wants to run or understand `git stash`.
- The user wants to run or understand `git clean -n -d`.
- The user wants to run or understand `git stash --index`.
- The user wants to run or understand `git stash --keep-index`.
- If you want to apply one of the older stashes, you can specify it by naming it, like this: `git stash apply stash@{2}`.
- If you want to remove those files too, such as to remove all `.o` files generated from a build so you can do a fully clean build, you can add a `-x` to the `clean` command.

## When NOT to use

- For recording changes to the repository, use the `git-recording-changes-to-the-repository` skill instead.
- For basic branching and merging, use the `git-basic-branching-and-merging` skill instead.
- For interactive staging, use the `git-interactive-staging` skill instead.

## Key concepts

- Stashing takes the dirty state of your working directory — that is, your modified tracked files and staged changes — and saves it on a stack of unfinished changes that you can reapply at any time (even on a different branch).
- In this case, you had a clean working directory when you tried to apply the stash, and you tried to apply it on the same branch you saved it from.
- To do that, you must run the `git stash apply` command with a `--index` option to tell the command to try to reapply the staged changes.
- By default, `git stash` will stash only modified and staged tracked files.
- A safer option is to run `git stash --all` to remove everything but save it in a stash.
- To remove all the untracked files in your working directory, you can run `git clean -f -d`, which removes any files and also any subdirectories that become empty as a result.
- By default, the `git clean` command will only remove untracked files that are not ignored.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git stash drop stash@{0}`
- You’ll want to be pretty careful with this command, since it’s designed to remove files from your working directory that are not tracked.
- 'force' or “really do this,” and is required if the Git configuration variable `clean.requireForce` is not explicitly set to false.
- The other way you can be careful about the process is to run it with the `-i` or “interactive” flag.

## Procedures

### Stashing Your Work

**Goal:** If you want to apply one of the older stashes, you can specify it by naming it, like this: `git stash apply stash@{2}`.

**Steps:**

1. If you run `git status`, you can see your dirty state:
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
       modified:   index.html
   Changes not staged for commit:
   ```
2. To push a new stash onto your stack, run `git stash` or `git stash push`:
   ```bash
   git stash
   ```
   Expected output (excerpt):
   ```text
   Saved working directory and index state \
     "WIP on master: 049d078 Create index file"
   HEAD is now at 049d078 Create index file
   (To restore them type "git stash apply")
   ```
3. You can now see that your working directory is clean:
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   # On branch master
   nothing to commit, working directory clean
   ```
4. To see which stashes you’ve stored, you can use `git stash list`:
   ```bash
   git stash list
   ```
   Expected output (excerpt):
   ```text
   stash@{0}: WIP on master: 049d078 Create index file
   stash@{1}: WIP on master: c264051 Revert "Add file_size"
   stash@{2}: WIP on master: 21d80a5 Add number to log
   ```
5. If you don’t specify a stash, Git assumes the most recent stash and tries to apply it:
   ```bash
   git stash apply
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Changes not staged for commit:
     (use "git add <file>..." to update what will be committed)
     (use "git checkout -- <file>..." to discard changes in working directory)
   ```
6. If you had run that instead, you’d have gotten back to your original position:
   ```bash
   git stash apply --index
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
       modified:   index.html
   ```

_1 more step(s) in references/procedures.md._

**Verify:** run `git stash list` - expect something like:
```text
stash@{0}: WIP on master: 049d078 Create index file
stash@{1}: WIP on master: c264051 Revert "Add file_size"
stash@{2}: WIP on master: 21d80a5 Add number to log
```

**If it fails:** You can see that Git re-modifies the files you reverted when you saved the stash.

### Creative Stashing

**Goal:** The first option that is quite popular is the `--keep-index` option to the `git stash` command.

**Steps:**

1. This tells Git to not only include all staged content in the stash being created, but simultaneously leave it in the index.
   ```bash
   git status -s
   git stash --keep-index
   git status -s
   ```
   Expected output (excerpt):
   ```text
   M  index.html
    M lib/simplegit.rb
   Saved working directory and index state WIP on master: 1b65b17 added the index file
   HEAD is now at 1b65b17 added the index file
   ```
2. Run:
   ```text
   M  index.html
   ```
3. However, including untracked files in the stash will still not include explicitly ignored files; to additionally include ignored files, use `--all` (or just `-a`).
   ```bash
   git status -s
   git stash -u
   git status -s
   ```
   Expected output (excerpt):
   ```text
   M  index.html
    M lib/simplegit.rb
   ?? new-file.txt
   Saved working directory and index state WIP on master: 1b65b17 added the index file
   ```
4. Finally, if you specify the `--patch` flag, Git will not stash everything that is modified but will instead prompt you interactively which of the changes you would like to stash and which you would like to keep in your working directory.
   ```bash
   git stash --patch
   ```
   Expected output (excerpt):
   ```text
   diff --git a/lib/simplegit.rb b/lib/simplegit.rb
   index 66d332e..8bb5674 100644
   --- a/lib/simplegit.rb
   +++ b/lib/simplegit.rb
   ```

### Creating a Branch from a Stash

**Goal:** This is a nice shortcut to recover stashed work easily and work on it in a new branch.

**Steps:**

1. If you want an easier way to test the stashed changes again, you can run `git stash branch <new branchname>`, which creates a new branch for you with your selected branch name, checks out the commit you were on when you stashed your work, reapplies your work there, and then drops the stash if it applies successfully:
   ```bash
   git stash branch testchanges
   ```
   Expected output (excerpt):
   ```text
   M   index.html
   M   lib/simplegit.rb
   Switched to a new branch 'testchanges'
   On branch testchanges
   ```

**If it fails:** If the apply tries to modify a file that you’ve since modified, you’ll get a merge conflict and will have to try to resolve it.

### Cleaning your Working Directory

**Goal:** If you want to remove those files too, such as to remove all `.o` files generated from a build so you can do a fully clean build, you can add a `-x` to the `clean` command.

**Steps:**

1. If you ever want to see what it would do, you can run the command with the `--dry-run` (or `-n`) option, which means “do a dry run and tell me what you would have removed”.
   ```bash
   git clean -d -n
   ```
   Expected output (excerpt):
   ```text
   Would remove test.o
   Would remove tmp/
   ```
2. If you want to remove those files too, such as to remove all `.o` files generated from a build so you can do a fully clean build, you can add a `-x` to the `clean` command.
   ```bash
   git status -s
   git clean -n -d
   git clean -n -d -x
   ```
   Expected output (excerpt):
   ```text
    M lib/simplegit.rb
   ?? build.TMP
   ?? tmp/
   Would remove build.TMP
   ```
3. This will run the `clean` command in an interactive mode.
   ```bash
   git clean -x -i
   ```
   Expected output (excerpt):
   ```text
   Would remove the following items:
     build.TMP  test.o
   *** Commands ***
       1: clean                2: filter by pattern    3: select by numbers    4: ask
   ```

More procedures in [references/procedures.md](references/procedures.md):

- Stashing Your Work

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git stash` | The answer to this issue is the `git stash` command. | `git stash` |
| `git status -s` | This tells Git to not only include all staged content in the stash being created, but simultaneously leave it in the index. | `git status -s` |
| `git status` | If you run `git status`, you can see your dirty state | `git status` |
| `git clean -n -d` | If you want to remove those files too, such as to remove all `.o` files generated from a build so you can do a fully clean build, you can add a `-x` to the `clean` command. | `git clean -n -d` |
| `git stash --index` | If you had run that instead, you’d have gotten back to your original position | `git stash apply --index` |
| `git stash --keep-index` | This tells Git to not only include all staged content in the stash being created, but simultaneously leave it in the index. | `git stash --keep-index` |
| `git stash -u` | However, including untracked files in the stash will still not include explicitly ignored files; to additionally include ignored files, use `--all` (or just `-a`). | `git stash -u` |
| `git stash --patch` | Finally, if you specify the `--patch` flag, Git will not stash everything that is modified but will instead prompt you interactively which of the changes you would like to stash and which you would like to keep in your working directory. | `git stash --patch` |
| `git clean -d -n` | If you ever want to see what it would do, you can run the command with the `--dry-run` (or `-n`) option, which means “do a dry run and tell me what you would have removed”. | `git clean -d -n` |
| `git clean -x -i` | This will run the `clean` command in an interactive mode. | `git clean -x -i` |

## Decision guide

- If you don’t know what the `git clean` command is going to do, always run it with a `-n` first to double check before changing the `-n` to a `-f` and doing it for real.

## Troubleshooting

- **Note:** Migrating to `git stash push` As of late October 2017, there has been extensive discussion on the Git mailing list, wherein the command `git stash save` is being deprecated in favour of the existing alternative `git stash push`. The main reason for this is that `git stash push` introduces the option of stashing selected pathspecs, something `git stash save` does not support.
- **Note:** There is a quirky situation where you might need to be extra forceful in asking Git to clean your working directory. If you happen to be in a working directory under which you’ve copied or cloned other Git repositories (perhaps as submodules), even `git clean -fd` will refuse to delete those directories. In cases like that, you need to add a second `-f` option for emphasis.

## Related skills

- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-basic-branching-and-merging` - Basic Branching and Merging
- `git-interactive-staging` - Interactive Staging
- `git-advanced-merging` - Advanced Merging

## Source

"Pro Git", pages 236-242. Sections: Stashing and Cleaning; Stashing and Cleaning > Stashing Your Work; Stashing and Cleaning > Creative Stashing; Stashing and Cleaning > Creating a Branch from a Stash; Stashing and Cleaning > Cleaning your Working Directory.
