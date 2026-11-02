---
name: git-rewriting-history
description: "Rewriting History playbook extracted from \"Pro Git\". filter-branch is the tool you probably want to use to scrub your entire history. Use when the user asks about rewriting history, commit message, git rebase, git commit, git applies, history, single commit; or mentions git commit --amend, git rebase -i, git log --pretty, git rebase --continue, git add, git commit -m."
---

# Rewriting History

`filter-branch` is the tool you probably want to use to scrub your entire history.

_Built from "Pro Git" (pages 249-257) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **rewriting history** (commit message, git rebase, git commit, git applies, history).
- The user wants to run or understand `git commit --amend`.
- The user wants to run or understand `git rebase -i`.
- The user wants to run or understand `git log --pretty`.
- The user wants to run or understand `git rebase --continue`.
- Git doesn’t have a modify-history tool, but you can use the rebase tool to rebase a series of commits onto the HEAD that they were originally based on instead of moving them to another one.
- There is another history-rewriting option that you can use if you need to rewrite a larger number of commits in some scriptable way — for instance, changing your email address globally or removing a file from every commit.

## When NOT to use

- The command is `filter-branch`, and it can rewrite huge swaths of your history, so you probably shouldn’t use it unless your project isn’t yet public and other people haven’t based work off the commits you’re about to rewrite.
- For rebasing, use the `git-rebasing` skill instead.
- For contributing to a project, use the `git-distributed-git-contributing-to-a-project` skill instead.
- For recording changes to the repository, use the `git-recording-changes-to-the-repository` skill instead.

## Key concepts

- Changing your most recent commit is probably the most common rewriting of history that you’ll do.
- Git doesn’t have a modify-history tool, but you can use the rebase tool to rebase a series of commits onto the HEAD that they were originally based on instead of moving them to another one.
- You must indicate how far back you want to rewrite commits by telling the command which commit to rebase onto.
- Because of the way Git builds commit objects, deleting or altering a commit will cause the rewriting of all the commits that follow it.
- There is another history-rewriting option that you can use if you need to rewrite a larger number of commits in some scriptable way — for instance, changing your email address globally or removing a file from every commit.
- Because commits contain the SHA-1 values of their parents, this command changes every commit SHA-1 in your history, not just those that have the matching email address.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git commit --amend`
  - `git commit --amend --no-edit`
  - `git rebase -i HEAD~3`
  - `git rebase --continue`
  - `git filter-branch --tree-filter 'rm -f passwords.txt' HEAD`
  - `git filter-branch --subdirectory-filter trunk HEAD`
  - `git filter-branch --commit-filter '`
- **Note (from source):** Don’t push your work until you’re happy with it One of the cardinal rules of Git is that, since so much work is local within your clone, you have a great deal of freedom to rewrite your history locally. However, once you push your work, it is a different story entirely, and you should consider pushed work as final unless you have good reason to change it. In short, you should avoid pushing your work until you’re happy with it and ready to share it with the rest of the world.
- **Caution (from source):** `git filter-branch` has many pitfalls, and is no longer the recommended way to rewrite history. Instead, consider using `git-filter-repo`, which is a Python script that does a better job for most applications where you would normally turn to `filter-branch`.
- **Caution (from source):** https://github.com/newren/git-filter-repo.
- Changing your most recent commit is probably the most common rewriting of history that you’ll do.
- You need to be careful with this technique because amending changes the SHA-1 of the commit.
- Don’t include any commit you’ve already pushed to a central server — doing so will confuse other developers by providing an alternate version of the same change.

## Procedures

### Changing the Last Commit

**Goal:** Changing your most recent commit is probably the most common rewriting of history that you’ll do.

**Steps:**

1. If you simply want to modify your last commit message, that’s easy:
   ```bash
   git commit --amend
   ```
2. On the other hand, if your amendments are suitably trivial (fixing a silly typo or adding a file you forgot to stage) such that the earlier commit message is just fine, you can simply make the changes, stage them, and avoid the unnecessary editor session entirely with:
   ```bash
   git commit --amend --no-edit
   ```

**If it fails:** On the other hand, if your amendments are suitably trivial (fixing a silly typo or adding a file you forgot to stage) such that the earlier commit message is just fine, you can simply make the changes, stage them, and avoid the unnecessary editor session entirely with:

### Changing Multiple Commit Messages

**Goal:** Git doesn’t have a modify-history tool, but you can use the rebase tool to rebase a series of commits onto the HEAD that they were originally based on instead of moving them to another one.

**Steps:**

1. It may be easier to remember the `~3` because you’re trying to edit the last three commits, but keep in mind that you’re actually designating four commits ago, the parent of the last commit you want to edit:
   ```bash
   git rebase -i HEAD~3
   ```
2. Running this command gives you a list of commits in your text editor that looks something like this:
   ```text
   pick f7f3f6d Change my name a bit
   pick 310154e Update README formatting and add blame
   pick a5f4a0d Add cat-file
   # Rebase 710f0f8..a5f4a0d onto 710f0f8
   #
   # Commands:
   # p, pick <commit> = use commit
   # r, reword <commit> = use commit, but edit the commit message
   # e, edit <commit> = use commit, but stop for amending
   # s, squash <commit> = use commit, but meld into previous commit
   # f, fixup <commit> = like "squash", but discard this commit's log message
   # x, exec <command> = run command (the rest of the line) using shell
   # b, break = stop here (continue rebase later with 'git rebase --continue')
   # d, drop <commit> = remove commit
   # l, label <label> = label current HEAD with a name
   # ... (full listing in references)
   ```
3. If you run a `log`, you see something like this:
   ```bash
   git log --pretty=format:"%h %s" HEAD~3..HEAD
   ```
   Expected output (excerpt):
   ```text
   a5f4a0d Add cat-file
   310154e Update README formatting and add blame
   f7f3f6d Change my name a bit
   ```
4. For example, to modify only the third commit message, you change the file to look like this:
   ```text
   edit f7f3f6d Change my name a bit
   pick 310154e Update README formatting and add blame
   pick a5f4a0d Add cat-file
   ```
5. When you save and exit the editor, Git rewinds you back to the last commit in that list and drops you on the command line with the following message:
   ```bash
   git rebase -i HEAD~3
   ```
   Expected output (excerpt):
   ```text
   Stopped at f7f3f6d... Change my name a bit
   You can amend the commit now, with
          git commit --amend
   Once you're satisfied with your changes, run
   ```
6. Type:
   ```bash
   git commit --amend
   ```

_1 more step(s) in references/procedures.md._

**Verify:** run `git log --pretty=format:"%h %s" HEAD~3..HEAD` - expect something like:
```text
a5f4a0d Add cat-file
310154e Update README formatting and add blame
f7f3f6d Change my name a bit
```

### Reordering Commits

**Goal:** Reordering Commits

**Steps:**

1. If you want to remove the “Add cat-file” commit and change the order in which the other two commits are introduced, you can change the rebase script from this:
   ```text
   pick f7f3f6d Change my name a bit
   pick 310154e Update README formatting and add blame
   pick a5f4a0d Add cat-file
   ```
2. to this:
   ```text
   pick 310154e Update README formatting and add blame
   pick f7f3f6d Change my name a bit
   ```

### Squashing Commits

**Goal:** Squashing Commits

**Steps:**

1. The script puts helpful instructions in the rebase message:
   ```text
   #
   # Commands:
   # p, pick <commit> = use commit
   # r, reword <commit> = use commit, but edit the commit message
   # e, edit <commit> = use commit, but stop for amending
   # s, squash <commit> = use commit, but meld into previous commit
   # f, fixup <commit> = like "squash", but discard this commit's log message
   # x, exec <command> = run command (the rest of the line) using shell
   # b, break = stop here (continue rebase later with 'git rebase --continue')
   # d, drop <commit> = remove commit
   # l, label <label> = label current HEAD with a name
   # t, reset <label> = reset HEAD to a label
   # m, merge [-C <commit> | -c <commit>] <label> [# <oneline>]
   # .       create a merge commit using the original merge commit's
   # .       message (or the oneline, if no original merge commit was
   # ... (full listing in references)
   ```
2. So, if you want to make a single commit from these three commits, you make the script look like this:
   ```text
   pick f7f3f6d Change my name a bit
   squash 310154e Update README formatting and add blame
   squash a5f4a0d Add cat-file
   ```
3. When you save and exit the editor, Git applies all three changes and then puts you back into the editor to merge the three commit messages:
   ```text
   # This is a combination of 3 commits.
   # The first commit's message is:
   ```
4. Run:
   ```text
   Change my name a bit
   # This is the 2nd commit message:
   Update README formatting and add blame
   # This is the 3rd commit message:
   Add cat-file
   ```

### Splitting a Commit

**Goal:** Splitting a Commit

**Steps:**

1. You can do that in the `rebase -i` script by changing the instruction on the commit you want to split to “edit”:
   ```text
   pick f7f3f6d Change my name a bit
   edit 310154e Update README formatting and add blame
   pick a5f4a0d Add cat-file
   ```
2. Now you can stage and commit files until you have several commits, and run `git rebase --continue` when you’re done:
   ```bash
   git reset HEAD^
   git add README
   git commit -m 'Update README formatting'
   git add lib/simplegit.rb
   git commit -m 'Add blame'
   git rebase --continue
   ```
3. Git applies the last commit (`a5f4a0d`) in the script, and your history looks like this:
   ```bash
   git log -4 --pretty=format:"%h %s"
   ```
   Expected output (excerpt):
   ```text
   1c002dd Add cat-file
   9b29157 Add blame
   ```
4. Run:
   ```text
   35cfb2b Update README formatting
   f7f3f6d Change my name a bit
   ```

**Verify:** run `git log -4 --pretty=format:"%h %s"` - expect something like:
```text
1c002dd Add cat-file
9b29157 Add blame
```

More procedures in [references/procedures.md](references/procedures.md):

- Changing Multiple Commit Messages
- Squashing Commits
- Deleting a commit
- The Nuclear Option: filter-branch

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git commit --amend` | If, on the other hand, you want to change the actual content of your last commit, the process works basically the same way — first make the changes you think you forgot, stage those changes, and the subsequent `git commit --amend`replaces that last commit with your new, improved commit. | `git commit --amend` |
| `git rebase -i` | For example, if you want to change the last three commit messages, or any of the commit messages in that group, you supply as an argument to `git rebase -i` the parent of the last commit you want to edit, which is `HEAD~2^` or `HEAD~3`. | `git rebase -i HEAD~3` |
| `git log --pretty` | If you run a `log`, you see something like this | `git log -4 --pretty=format:"%h %s"` |
| `git rebase --continue` | Now you can stage and commit files until you have several commits, and run `git rebase --continue` when you’re done | `git rebase --continue` |
| `git add` | Someone accidentally commits a huge binary file with a thoughtless `git add .`, and you want to remove it everywhere. | `git add README` |
| `git commit -m` | Now you can stage and commit files until you have several commits, and run `git rebase --continue` when you’re done | `git commit -m 'Add blame'` |
| `git commit --amend --no-edit` | On the other hand, if your amendments are suitably trivial (fixing a silly typo or adding a file you forgot to stage) such that the earlier commit message is just fine, you can simply make the changes, stage them, and avoid the unnecessary editor session entirely with | `git commit --amend --no-edit` |
| `git reset` | There, you can do a mixed reset of that commit with `git reset HEAD^`, which effectively undoes that commit and leaves the modified files unstaged. | `git reset HEAD^` |
| `git filter-branch --tree-filter -f` | To remove a file named `passwords.txt` from your entire history, you can use the `--tree-filter` option to `filter-branch` | `git filter-branch --tree-filter 'rm -f passwords.txt' HEAD` |
| `git filter-branch --subdirectory-filter` | If you want to make the `trunk` subdirectory be the new project root for every commit, `filter-branch` can help you do that, too | `git filter-branch --subdirectory-filter trunk HEAD` |
| `git filter-branch --commit-filter` | You need to be careful to change only the email addresses that are yours, so you use `--commit-filter` | `git filter-branch --commit-filter '` |

## Decision guide

- Git doesn’t have a modify-history tool, but you can use the rebase tool to rebase a series of commits onto the HEAD that they were originally based on instead of moving them to another one.
- If, instead of “pick” or “edit”, you specify “squash”, Git applies both that change and the change directly before it and makes you merge the commit messages together.
- Instead of “Update README formatting and add blame”, you want to split it into two commits: “Update README formatting” for the first, and “Add blame” for the second.
- If you get partway through a rebase like this and decide it’s not a good idea, you can always stop.

## Troubleshooting

- **Tip:** An amended commit may (or may not) need an amended commit message When you amend a commit, you have the opportunity to change both the commit message and the content of the commit. If you amend the content of the commit substantially, you should almost certainly update the commit message to reflect that amended content.
- **Note:** Drew DeVault made a practical hands-on guide with exercises to learn how to use `git rebase`. You can find it at: https://git-rebase.io/

## Related skills

- `git-rebasing` - Rebasing
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-as-a-client` - Git as a Client

## Source

"Pro Git", pages 249-257. Sections: Rewriting History; Rewriting History > Changing the Last Commit; Rewriting History > Changing Multiple Commit Messages; Rewriting History > Reordering Commits; Rewriting History > Squashing Commits; Rewriting History > Splitting a Commit; Rewriting History > Deleting a commit; Rewriting History > The Nuclear Option: filter-branch.
