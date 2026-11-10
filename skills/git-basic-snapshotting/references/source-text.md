# Source text: Basic Snapshotting

_Cleaned extract from "Pro Git"._

## Basic Snapshotting (pages 487-487)

For the basic workflow of staging content and committing it to your history, there are only a few basic commands.

## Basic Snapshotting > git add (pages 487-487)

The `git add` command adds content from the working directory into the staging area (or “index”) for the next commit. When the `git commit` command is run, by default it only looks at this staging area, so `git add` is used to craft what exactly you would like your next commit snapshot to look like.

This command is an incredibly important command in Git and is mentioned or used dozens of times in this book. We’ll quickly cover some of the unique uses that can be found.

We first introduce and explain `git add` in detail in Tracking New Files.

We mention how to use it to resolve merge conflicts in Basic Merge Conflicts.

We go over using it to interactively stage only specific parts of a modified file in Interactive Staging.

Finally, we emulate it at a low level in Tree Objects, so you can get an idea of what it’s doing behind the scenes.

## Basic Snapshotting > git status (pages 487-487)

The `git status` command will show you the different states of files in your working directory and staging area. Which files are modified and unstaged and which are staged but not yet committed. In its normal form, it also will show you some basic hints on how to move files between these stages.

We first cover `status` in Checking the Status of Your Files, both in its basic and simplified forms.

While we use it throughout the book, pretty much everything you can do with the `git status` command is covered there.

## Basic Snapshotting > git diff (pages 487-488)

The `git diff` command is used when you want to see differences between any two trees. This could be the difference between your working environment and your staging area (`git diff` by itself), between your staging area and your last commit (`git diff --staged`), or between two commits (`gitdiff master branchB`).

We first look at the basic uses of `git diff` in Viewing Your Staged and Unstaged Changes, where we show how to see what changes are staged and which are not yet staged.

We use it to look for possible whitespace issues before committing with the `--check` option in

Commit Guidelines.

We see how to check the differences between branches more effectively with the `git diff A…B` syntax in Determining What Is Introduced.

We use it to filter out whitespace differences with `-b` and how to compare different stages of conflicted files with `--theirs`, `--ours` and `--base` in Advanced Merging.

Finally, we use it to effectively compare submodule changes with `--submodule` in Starting with

Submodules.

## Basic Snapshotting > git difftool (pages 488-488)

The `git difftool` command simply launches an external tool to show you the difference between two trees in case you want to use something other than the built in `git diff` command.

We only briefly mention this in Viewing Your Staged and Unstaged Changes.

## Basic Snapshotting > git commit (pages 488-488)

The `git commit` command takes all the file contents that have been staged with `git add` and records a new permanent snapshot in the database and then moves the branch pointer on the current branch up to it.

We first cover the basics of committing in Committing Your Changes. There we also demonstrate how to use the `-a` flag to skip the `git add` step in daily workflows and how to use the `-m` flag to pass a commit message in on the command line instead of firing up an editor.

In Undoing Things we cover using the `--amend` option to redo the most recent commit.

In Branches in a Nutshell, we go into much more detail about what `git commit` does and why it does it like that.

We looked at how to sign commits cryptographically with the `-S` flag in Signing Commits.

Finally, we take a look at what the `git commit` command does in the background and how it’s actually implemented in Commit Objects.

## Basic Snapshotting > git reset (pages 488-489)

The `git reset` command is primarily used to undo things, as you can possibly tell by the verb. It moves around the `HEAD` pointer and optionally changes the `index` or staging area and can also optionally change the working directory if you use `--hard`. This final option makes it possible for this command to lose your work if used incorrectly, so make sure you understand it before using it.

We first effectively cover the simplest use of `git reset` in Unstaging a Staged File, where we use it to unstage a file we had run `git add` on.

We then cover it in quite some detail in Reset Demystified, which is entirely devoted to explaining this command.

We use `git reset --hard` to abort a merge in Aborting a Merge, where we also use `git merge--abort`, which is a bit of a wrapper for the `git reset` command.

## Basic Snapshotting > git rm (pages 489-489)

The `git rm` command is used to remove files from the staging area and working directory for Git. It is similar to `git add` in that it stages a removal of a file for the next commit.

We cover the `git rm` command in some detail in Removing Files, including recursively removing files and only removing files from the staging area but leaving them in the working directory with `--cached`.

The only other differing use of `git rm` in the book is in Removing Objects where we briefly use and explain the `--ignore-unmatch` when running `git filter-branch`, which simply makes it not error out when the file we are trying to remove doesn’t exist. This can be useful for scripting purposes.

## Basic Snapshotting > git mv (pages 489-489)

The `git mv` command is a thin convenience command to move a file and then run `git add` on the new file and `git rm` on the old file.

We only briefly mention this command in Moving Files.

## Basic Snapshotting > git clean (pages 489-489)

The `git clean` command is used to remove unwanted files from your working directory. This could include removing temporary build artifacts or merge conflict files.

We cover many of the options and scenarios in which you might used the clean command in

Cleaning your Working Directory.
