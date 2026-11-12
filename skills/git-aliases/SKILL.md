---
name: git-aliases
description: "Create shortcuts for git commands with git config alias (git co, git unstage, git last). Use when the user wants a git alias or shorter git commands."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git Aliases"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "66-68"
---

# Git Aliases

As you go on using Git, you’ll probably use other commands frequently as well; don’t hesitate to create new aliases.

_Built from "Pro Git" (pages 66-68) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **git aliases** (n’t automatically infer, git commands, git config, alias, git commit).
- The user wants to run or understand `git config --global`.
- The user wants to run or understand `git unstage`.
- The user wants to run or understand `git reset`.
- The user wants to run or understand `git last`.

## When NOT to use

- For reset demystified, use the `git-reset-demystified` skill instead.
- For git configuration, use the `git-configuration` skill instead.
- For undoing things, use the `git-undoing-things` skill instead.

## Key concepts

- Git doesn’t automatically infer your command if you type it in partially.
- If you don’t want to type the entire text of each of the Git commands, you can easily set up an alias for each command using `git config`.
- This means that, for example, instead of typing `git commit`, you just need to type `git ci`.
- This technique can also be very useful in creating commands that you think should exist.
- As you can tell, Git simply replaces the new command with whatever you alias it for.
- However, maybe you want to run an external command, rather than a Git subcommand.
- In that case, you start the command with a `!` character.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Git Aliases

**Goal:** As you go on using Git, you’ll probably use other commands frequently as well; don’t hesitate to create new aliases.

**Steps:**

1. Here are a couple of examples you may want to set up:
   ```bash
   git config --global alias.co checkout
   git config --global alias.br branch
   git config --global alias.ci commit
   git config --global alias.st status
   ```
2. For example, to correct the usability problem you encountered with unstaging a file, you can add your own unstage alias to Git:
   ```bash
   git config --global alias.unstage 'reset HEAD --'
   ```
3. This makes the following two commands equivalent:
   ```bash
   git unstage fileA
   git reset HEAD -- fileA
   ```
4. It’s also common to add a `last` command, like this:
   ```bash
   git config --global alias.last 'log -1 HEAD'
   ```
5. This way, you can see the last commit easily:
   ```bash
   git last
   ```
   Expected output (excerpt):
   ```text
   commit 66938dae3329c7aebe598c2246a8e6af90d04646
   Author: Josh Goebel <dreamer3@example.com>
   Date:   Tue Aug 26 19:48:51 2008 +0800
       Test for current head
   ```
6. We can demonstrate by aliasing `git visual` to run `gitk`:
   ```bash
   git config --global alias.visual '!gitk'
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git config --global` | Here are a couple of examples you may want to set up | `git config --global alias.br branch` |
| `git unstage` | This makes the following two commands equivalent | `git unstage fileA` |
| `git reset` | This makes the following two commands equivalent | `git reset HEAD -- fileA` |
| `git last` | This way, you can see the last commit easily | `git last` |

## Decision guide

- This means that, for example, instead of typing `git commit`, you just need to type `git ci`.

## Related skills

- `git-reset-demystified` - Reset Demystified
- `git-configuration` - Git Configuration
- `git-undoing-things` - Undoing Things
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository

## Source

"Pro Git", pages 66-68. Sections: Git Aliases.
