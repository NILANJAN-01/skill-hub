---
name: git-getting-a-git-repository
description: "Getting a Git Repository playbook extracted from \"Pro Git\". This is an important distinction — instead of getting just a working copy, Git receives a full copy of nearly all data that the server has. Use when the user asks about getting a git repository, git repository, git clone, existing git, files, project, typically obtain; or mentions cd, git add, git clone, git init, git commit -m."
---

# Getting a Git Repository

This is an important distinction — instead of getting just a working copy, Git receives a full copy of nearly all data that the server has.

_Built from "Pro Git" (pages 32-34) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **getting a git repository** (git repository, git clone, existing git, files, project).
- The user wants to run or understand `cd`.
- The user wants to run or understand `git add`.
- The user wants to run or understand `git clone`.
- The user wants to run or understand `git init`.
- If you want to get a copy of an existing Git repository — for example, a project you’d like to contribute to — the command you need is `git clone`.

## When NOT to use

- For getting git on a server, use the `git-getting-git-on-a-server` skill instead.
- For the protocols, use the `git-the-protocols` skill instead.
- For recording changes to the repository, use the `git-recording-changes-to-the-repository` skill instead.

## Key concepts

- 1.You can take a local directory that is currently not under version control, and turn it into a Git repository, or
- 2.You can clone an existing Git repository from elsewhere.
- This creates a new subdirectory named `.git` that contains all of your necessary repository files — a
- If you want to get a copy of an existing Git repository — for example, a project you’d like to contribute to — the command you need is `git clone`.
- You clone a repository with `git clone <url>`.
- That creates a directory named `libgit2`, initializes a `.git` directory inside it, pulls down all the data for that repository, and checks out a working copy of the latest version.
- Getting Git on a Server will introduce all of the available options the server can set up to access your Git repository and the pros and cons of each.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Initializing a Repository in an Existing Directory

**Goal:** This creates a new subdirectory named `.git` that contains all of your necessary repository files — a

**Steps:**

1. for Linux:
   ```bash
   cd /home/user/my_project
   ```
2. for macOS:
   ```bash
   cd /Users/user/my_project
   ```
3. for Windows:
   ```bash
   cd C:/Users/user/my_project
   ```
4. and type:
   ```bash
   git init
   ```
5. You can accomplish that with a few `git add` commands that specify the files you want to track, followed by a `git commit`:
   ```bash
   git add *.c
   git add LICENSE
   git commit -m 'Initial project version'
   ```

### Cloning an Existing Repository

**Goal:** If you want to get a copy of an existing Git repository — for example, a project you’d like to contribute to — the command you need is `git clone`.

**Steps:**

1. For example, if you want to clone the Git linkable library called `libgit2`, you can do so like this:
   ```bash
   git clone https://github.com/libgit2/libgit2
   ```
2. If you want to clone the repository into a directory named something other than `libgit2`, you can specify the new directory name as an additional argument:
   ```bash
   git clone https://github.com/libgit2/libgit2 mylibgit
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git add` | You can accomplish that with a few `git add` commands that specify the files you want to track, followed by a `git commit` | `git add *.c` |
| `git clone` | If you want to get a copy of an existing Git repository — for example, a project you’d like to contribute to — the command you need is `git clone`. | `git clone https://github.com/libgit2/libgit2` |
| `git init` | and type | `git init` |
| `git commit -m` | You can accomplish that with a few `git add` commands that specify the files you want to track, followed by a `git commit` | `git commit -m 'Initial project version'` |

## Decision guide

- If you want to start version-controlling existing files (as opposed to an empty directory), you should probably begin tracking those files and do an initial commit.
- This is an important distinction — instead of getting just a working copy, Git receives a full copy of nearly all data that the server has.

## Related skills

- `git-getting-git-on-a-server` - Getting Git on a Server
- `git-the-protocols` - The Protocols
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-submodules` - Submodules

## Source

"Pro Git", pages 32-34. Sections: Getting a Git Repository; Getting a Git Repository > Initializing a Repository in an Existing Directory; Getting a Git Repository > Cloning an Existing Repository.
