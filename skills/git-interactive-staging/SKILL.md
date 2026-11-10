---
name: git-interactive-staging
description: "Interactive Staging playbook extracted from \"Pro Git\". You can see that this command shows you a much different view of your staging area than you’re probably used to — basically, the same information you get with git status but a bit more succinct and informative. Use when the user asks about interactive staging, big messy commit, git add, staged files, staging, diff, unstaged; or mentions git add -i."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Interactive Staging"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "232-236"
---

# Interactive Staging

You can see that this command shows you a much different view of your staging area than you’re probably used to — basically, the same information you get with `git status` but a bit more succinct and informative.

_Built from "Pro Git" (pages 232-236) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **interactive staging** (big messy commit, git add, staged files, staging, diff).
- The user wants to run or understand `git add -i`.
- After this comes a “Commands” section, which allows you to do a number of things like staging and unstaging files, staging parts of files, adding untracked files, and displaying diffs of what has been staged.
- To see the diff of what you’ve staged, you can use the `d` or `6` (for diff) command.
- With these basic commands, you can use the interactive add mode to deal with your staging area a little more easily.
- Generally, you’ll type `y` or `n` if you want to stage each hunk, but staging all of them in certain files or skipping a hunk decision until later can be helpful too.

## When NOT to use

- For recording changes to the repository, use the `git-recording-changes-to-the-repository` skill instead.
- For undoing things, use the `git-undoing-things` skill instead.
- For basic snapshotting, use the `git-basic-snapshotting` skill instead.

## Key concepts

- After this comes a “Commands” section, which allows you to do a number of things like staging and unstaging files, staging parts of files, adding untracked files, and displaying diffs of what has been staged.
- The `*` next to each file means the file is selected to be staged.
- To see the diff of what you’ve staged, you can use the `d` or `6` (for diff) command.
- It shows you a list of your staged files, and you can select the ones for which you would like to see the staged diff.
- With these basic commands, you can use the interactive add mode to deal with your staging area a little more easily.
- It’s also possible for Git to stage certain parts of files and not the rest.
- You also don’t need to be in interactive add mode to do the partial-file staging — you can start the same script by using `git add -p` or `git add --patch` on the command line.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Interactive Staging

**Goal:** You can see that this command shows you a much different view of your staging area than you’re probably used to — basically, the same information you get with `git status` but a bit more succinct and informative.

**Steps:**

1. If you run `git add` with the `-i` or `--interactive` option, Git enters an interactive shell mode, displaying something like this:
   ```bash
   git add -i
   ```
   Expected output (excerpt):
   ```text
              staged     unstaged path
     1:    unchanged        +0/-1 TODO
     2:    unchanged        +1/-1 index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   ```

### Staging and Unstaging Files

**Goal:** The `*` next to each file means the file is selected to be staged.

**Steps:**

1. If you type `u` or `2` (for update) at the `What now>` prompt, you’re prompted for which files you want to stage:
   ```text
   What now> u
              staged     unstaged path
     1:    unchanged        +0/-1 TODO
   ```
2. Run:
   ```text
     2:    unchanged        +1/-1 index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   Update>>
   ```
3. To stage the `TODO` and `index.html` files, you can type the numbers:
   ```text
   Update>> 1,2
              staged     unstaged path
   * 1:    unchanged        +0/-1 TODO
   * 2:    unchanged        +1/-1 index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   Update>>
   ```
4. If you press Enter after typing nothing at the `Update>>` prompt, Git takes anything selected and stages it for you:
   ```text
   Update>>
   updated 2 paths
   *** Commands ***
     1: [s]tatus     2: [u]pdate      3: [r]evert     4: [a]dd untracked
     5: [p]atch      6: [d]iff        7: [q]uit       8: [h]elp
   What now> s
              staged     unstaged path
     1:        +0/-1      nothing TODO
     2:        +1/-1      nothing index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   ```
5. If you want to unstage the `TODO` file at this point, you use the `r` or `3` (for revert) option:
   ```text
   *** Commands ***
     1: [s]tatus     2: [u]pdate      3: [r]evert     4: [a]dd untracked
     5: [p]atch      6: [d]iff        7: [q]uit       8: [h]elp
   What now> r
              staged     unstaged path
     1:        +0/-1      nothing TODO
     2:        +1/-1      nothing index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   Revert>> 1
              staged     unstaged path
   * 1:        +0/-1      nothing TODO
     2:        +1/-1      nothing index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   Revert>> [enter]
   reverted one path
   ```
6. Looking at your Git status again, you can see that you’ve unstaged the `TODO` file:
   ```text
   *** Commands ***
     1: [s]tatus     2: [u]pdate      3: [r]evert     4: [a]dd untracked
     5: [p]atch      6: [d]iff        7: [q]uit       8: [h]elp
   What now> s
              staged     unstaged path
     1:    unchanged        +0/-1 TODO
     2:        +1/-1      nothing index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   ```

_1 more step(s) in references/procedures.md._

**If it fails:** If you want to unstage the `TODO` file at this point, you use the `r` or `3` (for revert) option:

### Staging Patches

**Goal:** Generally, you’ll type `y` or `n` if you want to stage each hunk, but staging all of them in certain files or skipping a hunk decision until later can be helpful too.

**Steps:**

1. Git will ask you which files you would like to partially stage; then, for each section of the selected files, it will display hunks of the file diff and ask if you would like to stage them, one by one:
   ```ruby
   diff --git a/lib/simplegit.rb b/lib/simplegit.rb
   index dd5ecc4..57399e0 100644
   --- a/lib/simplegit.rb
   +++ b/lib/simplegit.rb
   @@ -22,7 +22,7 @@ class SimpleGit
      end
      def log(treeish = 'master')
   -    command("git log -n 25 #{treeish}")
   +    command("git log -n 30 #{treeish}")
      end
      def blame(path)
   Stage this hunk [y,n,a,d,/,j,J,g,e,?]?
   ```
2. Typing `?` shows a list of what you can do:
   ```text
   Stage this hunk [y,n,a,d,/,j,J,g,e,?]? ?
   y - stage this hunk
   n - do not stage this hunk
   a - stage this and all the remaining hunks in the file
   d - do not stage this hunk nor any of the remaining hunks in the file
   g - select a hunk to go to
   / - search for a hunk matching the given regex
   j - leave this hunk undecided, see next undecided hunk
   J - leave this hunk undecided, see next hunk
   k - leave this hunk undecided, see previous undecided hunk
   K - leave this hunk undecided, see previous hunk
   s - split the current hunk into smaller hunks
   e - manually edit the current hunk
   ? - print help
   ```
3. If you stage one part of the file and leave another part unstaged, your status output will look like this:
   ```text
   What now> 1
              staged     unstaged path
     1:    unchanged        +0/-1 TODO
     2:        +1/-1      nothing index.html
     3:        +1/-1        +4/-0 lib/simplegit.rb
   ```

More procedures in [references/procedures.md](references/procedures.md):

- Staging and Unstaging Files

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git add -i` | If you run `git add` with the `-i` or `--interactive` option, Git enters an interactive shell mode, displaying something like this | `git add -i` |

## Related skills

- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-undoing-things` - Undoing Things
- `git-basic-snapshotting` - Basic Snapshotting
- `git-stashing-and-cleaning` - Stashing and Cleaning

## Source

"Pro Git", pages 232-236. Sections: Interactive Staging; Interactive Staging > Staging and Unstaging Files; Interactive Staging > Staging Patches.
