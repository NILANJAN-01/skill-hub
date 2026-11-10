# Git Basics

_Source: Pro Git, pages 32-68_

## Topics covered

- Getting a Git Repository
- Recording Changes to the Repository
- Viewing the Commit History
- Undoing Things
- Working with Remotes
- Tagging
- Git Aliases
- Summary

**Key terms:** contributing, file, commit, staged, tag, modified, git, committed, unstage, tracked

## Key points

- Git Basics If you can read only one chapter to get going with Git, this is it.
- Getting a Git Repository You typically obtain a Git repository in one of two ways: 1.
- See Git Internals for more information about exactly what files are contained in the .git directory you just created.
- You can accomplish that with a few git add commands that specify the files you want to track, followed by a git commit: `git add *.c`.
- Cloning an Existing Repository If you want to get a copy of an existing Git repository — for example, a project you’d like to contribute to — the command you need is git clone.
- To stage it, you run the git add command. git add is a multipurpose command — you use it to begin tracking new files, to stage files, and to do other things like marking merge-conflicted files as resolved.
- Let’s run git add now to stage the CONTRIBUTING.md file, and then run git status again: `git add CONTRIBUTING.md`.
- turns out that Git stages a file exactly as it is when you run the git add command.
- If you commit now, the version of CONTRIBUTING.md as it was when you last ran the git add command is how it will go into the commit, not the version of the file as it looks in your working directory when you run git commit.
- If you modify a file after you run git add, you have to run git add again to stage the latest version of the file: `git add CONTRIBUTING.md`.
- If you run git status -s or git status --short you get a far more simplified output from the command: `git status -s`.
- If you run your git status command, you once again see something like this: `git status`.
- Now you can use git diff to see what is still unstaged: `git diff`.
- The simplest way to commit is to type git commit: `git commit`.
- Adding the -a option to the git commit command makes Git automatically stage every file that is already tracked before doing the commit, letting you skip the git add part: `git status`.
- Then, if you run git rm, it stages the file’s removal: `git rm PROJECTS.md`.
- The git status command reminds you: `git add *`.
- Undoing things with git restore Git version 2.23.0 introduced a new command: git restore.
- From Git version 2.23.0 onwards, Git will use git restore instead of git reset for many undo operations.
- The git status command reminds you: `git add *`.
- To add a new remote Git repository as a shortname you can reference easily, run git remote add <shortname> <url>: `git remote`.
- When you’re using Git more heavily, however, you may see much more information from git remote show: `git remote show origin`.
- If you want to remove a remote for some reason — you’ve moved the server or are no longer using a particular mirror, or perhaps a contributor isn’t contributing anymore — you can either use git remote remove or git remote rm: `git remote remove paul`.
- You can see the tag data along with the commit that was tagged by using the git show command: `git show v1.4`.
- This means that, for example, instead of typing git commit, you just need to type git ci.

## Commands / code

```
$ cd /home/user/my_project
$ cd /Users/user/my_project
$ cd C:/Users/user/my_project
$ git init
$ git add *.c
$ git add LICENSE
$ git commit -m 'Initial project version'
$ git clone https://github.com/libgit2/libgit2
$ git clone https://github.com/libgit2/libgit2 mylibgit
$ git status
$ echo 'My Project' > README
$ git add README
$ git add CONTRIBUTING.md
$ vim CONTRIBUTING.md
$ git status -s
$ cat .gitignore
$ git diff
$ git diff --staged
$ echo '# test line' >> CONTRIBUTING.md
$ git diff --cached
$ git commit
$ git commit -m "Story 182: fix benchmarks for speed"
$ git commit -a -m 'Add new benchmarks'
$ rm PROJECTS.md
$ git rm PROJECTS.md
$ git rm --cached README
$ git rm log/\*.log
$ git rm \*~
$ git mv file_from file_to
$ git mv README.md README
$ mv README.md README
$ git rm README.md
$ git clone https://github.com/schacon/simplegit-progit
$ git log
$ git log -p -2
$ git log --stat
$ git log --pretty=oneline
$ git log --pretty=format:"%h - %an, %ar : %s"
$ git log --pretty=format:"%h %s" --graph
$ git log --since=2.weeks
```

## Rules, tips and warnings

- Git Basics If you can read only one chapter to get going with Git, this is it.
- You can take a local directory that is currently not under version control, and turn it into a Git repository, or 2.
- You can clone an existing Git repository from elsewhere.
- If you’ve never done this, it looks a little different depending on which system you’re running: for Linux: `cd /home/user/my_project`.
- If you want to start version-controlling existing files (as opposed to an empty directory), you should probably begin tracking those files and do an initial commit.
- You can accomplish that with a few git add commands that specify the files you want to track, followed by a git commit: `git add *.c`.
- Cloning an Existing Repository If you want to get a copy of an existing Git repository — for example, a project you’d like to contribute to — the command you need is git clone.
- This is an important distinction — instead of getting just a working copy, Git receives a full copy of nearly all data that the server has.
- In fact, if your server disk gets corrupted, you can often use nearly any of the clones on any client to set the server back to the state it was in when it was cloned (you may lose some server-side hooks and such, but all the versioned data would be there — see Getting Git on a Server for more details).
- For example, if you want to clone the Git linkable library called libgit2, you can do so like this: `git clone https://github.com/libgit2/libgit2`.
- If you want to clone the repository into a directory named something other than libgit2, you can specify the new directory name as an additional argument: `git clone https://github.com/libgit2/libgit2 mylibgit`.
- Git has a number of different transfer protocols you can use.
