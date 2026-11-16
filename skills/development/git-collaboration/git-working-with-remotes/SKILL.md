---
name: git-working-with-remotes
description: "Manage git remotes: add, show, fetch, pull, push, rename, remove. Use when you need to add or change a remote URL."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Working with Remotes"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "56-61"
---

# Working with Remotes

To see which remote servers you have configured, you can run the `git remote` command.

_Built from "Pro Git" (pages 56-61) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **working with remotes** (git remote, remote repositories, remote repository, remote git repository, merge).
- The user wants to run or understand `git remote`.
- The user wants to run or understand `git remote -v`.
- The user wants to run or understand `git fetch`.
- The user wants to run or understand `git clone`.
- If you want to see more information about a particular remote, you can use the `git remote show<remote>` command.

## When NOT to use

- For remote branches, use the `git-remote-branches` skill instead.
- For the refspec, use the `git-the-refspec` skill instead.
- For contributing to a project, use the `git-distributed-git-contributing-to-a-project` skill instead.

## Key concepts

- If you have more than one remote, the command lists them all.
- This may be an easier or more comfortable workflow for you; and by default, the `git clone` command automatically sets up your local `master` branch to track the remote `master` branch (or whatever the default branch is called) on the server you cloned from.
- The command for this is simple: `git push <remote> <branch>`.
- If you want to see more information about a particular remote, you can use the `git remote show<remote>` command.
- The command helpfully tells you that if you’re on the `master` branch and you run `git pull`, it will automatically merge the remote’s `master` branch into the local one after it has been fetched.
- It also lists all the remote references it has pulled down.
- It also shows you which remote branches on the server you don’t yet have, which remote branches you have that have been removed from the server, and multiple local branches that are able to merge automatically with their remote-tracking branch when you run `git pull`.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Showing Your Remotes

**Goal:** To see which remote servers you have configured, you can run the `git remote` command.

**Steps:**

1. If you’ve cloned your repository, you should at least see `origin` — that is the default name Git gives to the server you cloned from:
   ```bash
   git clone https://github.com/schacon/ticgit
   cd ticgit
   git remote
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'ticgit'...
   remote: Reusing existing pack: 1857, done.
   remote: Total 1857 (delta 0), reused 0 (delta 0)
   Receiving objects: 100% (1857/1857), 374.35 KiB | 268.00 KiB/s, done.
   ```
2. You can also specify `-v`, which shows you the URLs that Git has stored for the shortname to be used when reading and writing to that remote:
   ```bash
   git remote -v
   ```
   Expected output (excerpt):
   ```text
   origin  https://github.com/schacon/ticgit (fetch)
   origin  https://github.com/schacon/ticgit (push)
   ```
3. For example, a repository with multiple remotes for working with several collaborators might look something like this.
   ```bash
   cd grit
   git remote -v
   ```
   Expected output (excerpt):
   ```text
   bakkdoor  https://github.com/bakkdoor/grit (fetch)
   bakkdoor  https://github.com/bakkdoor/grit (push)
   cho45     https://github.com/cho45/grit (fetch)
   cho45     https://github.com/cho45/grit (push)
   ```

**Verify:** run `git remote -v` - expect something like:
```text
origin  https://github.com/schacon/ticgit (fetch)
origin  https://github.com/schacon/ticgit (push)
```

### Adding Remote Repositories

**Goal:** We’ve mentioned and given some demonstrations of how the `git clone` command implicitly adds the `origin` remote for you.

**Steps:**

1. To add a new remote Git repository as a shortname you can reference easily, run `git remote add <shortname> <url>`:
   ```bash
   git remote
   git remote add pb https://github.com/paulboone/ticgit
   git remote -v
   ```
   Expected output (excerpt):
   ```text
   origin
   origin  https://github.com/schacon/ticgit (fetch)
   origin  https://github.com/schacon/ticgit (push)
   pb  https://github.com/paulboone/ticgit (fetch)
   ```
2. For example, if you want to fetch all the information that Paul has but that you don’t yet have in your repository, you can run `git fetch pb`:
   ```bash
   git fetch pb
   ```
   Expected output (excerpt):
   ```text
   remote: Counting objects: 43, done.
   remote: Compressing objects: 100% (36/36), done.
   remote: Total 43 (delta 10), reused 31 (delta 5)
   Unpacking objects: 100% (43/43), done.
   ```

### Fetching and Pulling from Your Remotes

**Goal:** This may be an easier or more comfortable workflow for you; and by default, the `git clone` command automatically sets up your local `master` branch to track the remote `master` branch (or whatever the default branch is called) on the server you cloned from.

**Steps:**

1. As you just saw, to get data from your remote projects, you can run:
   ```bash
   git fetch <remote>
   ```

### Inspecting a Remote

**Goal:** If you want to see more information about a particular remote, you can use the `git remote show<remote>` command.

**Steps:**

1. If you run this command with a particular shortname, such as `origin`, you get something like this:
   ```bash
   git remote show origin
   ```
   Expected output (excerpt):
   ```text
   * remote origin
     Fetch URL: https://github.com/schacon/ticgit
     Push  URL: https://github.com/schacon/ticgit
     HEAD branch: master
   ```
2. Run:
   ```text
     Remote branches:
       master                               tracked
       dev-branch                           tracked
     Local branch configured for 'git pull':
       master merges with remote master
     Local ref configured for 'git push':
       master pushes to master (up to date)
   ```
3. When you’re using Git more heavily, however, you may see much more information from `git remote show`:
   ```bash
   git remote show origin
   ```
   Expected output (excerpt):
   ```text
   * remote origin
     URL: https://github.com/my-org/complex-project
     Fetch URL: https://github.com/my-org/complex-project
     Push  URL: https://github.com/my-org/complex-project
   ```

### Renaming and Removing Remotes

**Goal:** You can run `git remote rename` to change a remote’s shortname.

**Steps:**

1. For instance, if you want to rename `pb` to `paul`, you can do so with `git remote rename`:
   ```bash
   git remote rename pb paul
   git remote
   ```
   Expected output (excerpt):
   ```text
   origin
   paul
   ```
2. If you want to remove a remote for some reason — you’ve moved the server or are no longer using a particular mirror, or perhaps a contributor isn’t contributing anymore — you can either use `gitremote remove` or `git remote rm`:
   ```bash
   git remote remove paul
   git remote
   ```
   Expected output (excerpt):
   ```text
   origin
   ```

More procedures in [references/procedures.md](references/procedures.md):

- Pushing to Your Remotes

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git remote` | For instance, if you want to rename `pb` to `paul`, you can do so with `git remote rename` | `git remote` |
| `git remote -v` | You can also specify `-v`, which shows you the URLs that Git has stored for the shortname to be used when reading and writing to that remote | `git remote -v` |
| `git fetch` | For example, if you want to fetch all the information that Paul has but that you don’t yet have in your repository, you can run `git fetch pb` | `git fetch pb` |
| `git clone` | This may be an easier or more comfortable workflow for you; and by default, the `git clone` command automatically sets up your local `master` branch to track the remote `master` branch (or whatever the default branch is called) on the server you cloned from. | `git clone https://github.com/schacon/ticgit` |
| `git push` | The command for this is simple: `git push <remote> <branch>`. | `git push origin master` |

## Troubleshooting

- **Note:** Remote repositories can be on your local machine. It is entirely possible that you can be working with a “remote” repository that is, in fact, on the same host you are. The word “remote” does not necessarily imply that the repository is somewhere else on the network or Internet, only that it is
- **Note:** From Git version 2.27 onward, `git pull` will give a warning if the `pull.rebase` variable is not set. Git will keep warning you until you set the variable.

## Related skills

- `git-remote-branches` - Remote Branches
- `git-the-refspec` - The Refspec
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-branch-management` - Branch Management

## Source

"Pro Git", pages 56-61. Sections: Working with Remotes; Working with Remotes > Showing Your Remotes; Working with Remotes > Adding Remote Repositories; Working with Remotes > Fetching and Pulling from Your Remotes; Working with Remotes > Pushing to Your Remotes; Working with Remotes > Inspecting a Remote; Working with Remotes > Renaming and Removing Remotes.
