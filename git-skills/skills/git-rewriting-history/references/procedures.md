# More procedures: Rewriting History

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
   # t, reset <label> = reset HEAD to a label
   # m, merge [-C <commit> | -c <commit>] <label> [# <oneline>]
   # .       create a merge commit using the original merge commit's
   # .       message (or the oneline, if no original merge commit was
   # .       specified). Use -c <commit> to reword the commit message.
   #
   # These lines can be re-ordered; they are executed from top to bottom.
   #
   # If you remove a line here THAT COMMIT WILL BE LOST.
   #
   # However, if you remove everything, the rebase will be aborted.
   #
   # Note that empty commits are commented out
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
7. Then, run:
   ```bash
   git rebase --continue
   ```

**Verify:** run `git log --pretty=format:"%h %s" HEAD~3..HEAD` - expect something like:
```text
a5f4a0d Add cat-file
310154e Update README formatting and add blame
f7f3f6d Change my name a bit
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
   # .       specified). Use -c <commit> to reword the commit message.
   #
   # These lines can be re-ordered; they are executed from top to bottom.
   #
   # If you remove a line here THAT COMMIT WILL BE LOST.
   #
   # However, if you remove everything, the rebase will be aborted.
   #
   # Note that empty commits are commented out
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

### Deleting a commit

**Goal:** Because of the way Git builds commit objects, deleting or altering a commit will cause the rewriting of all the commits that follow it.

**Steps:**

1. In the list of commits, put the word “drop” before the commit you want to delete (or just delete that line from the rebase script):
   ```text
   pick 461cb2a This commit is OK
   drop 5aecc10 This commit is broken
   ```

**If it fails:** Type `git rebase --abort`, and your repo will be returned to the state it was in before you started the rebase.

### The Nuclear Option: filter-branch

**Goal:** There is another history-rewriting option that you can use if you need to rewrite a larger number of commits in some scriptable way — for instance, changing your email address globally or removing a file from every commit.

**Steps:**

1. To remove a file named `passwords.txt` from your entire history, you can use the `--tree-filter` option to `filter-branch`:
   ```bash
   git filter-branch --tree-filter 'rm -f passwords.txt' HEAD
   ```
   Expected output (excerpt):
   ```text
   Rewrite 6b9b3cf04e7c5686a9cb838c3f36a8cb6a0fc2bd (21/21)
   Ref 'refs/heads/master' was rewritten
   ```
2. If you want to make the `trunk` subdirectory be the new project root for every commit, `filter-branch` can help you do that, too:
   ```bash
   git filter-branch --subdirectory-filter trunk HEAD
   ```
   Expected output (excerpt):
   ```text
   Rewrite 856f0bf61e41a27326cdae8f09fe708d679f596f (12/12)
   Ref 'refs/heads/master' was rewritten
   ```
3. You need to be careful to change only the email addresses that are yours, so you use `--commit-filter`:
   ```bash
   git filter-branch --commit-filter '
   ```
   Expected output (excerpt):
   ```text
           if [ "$GIT_AUTHOR_EMAIL" = "schacon@localhost" ];
           then
                   GIT_AUTHOR_NAME="Scott Chacon";
   ```
4. Run:
   ```text
                   GIT_AUTHOR_EMAIL="schacon@example.com";
                   git commit-tree "$@";
           else
                   git commit-tree "$@";
           fi' HEAD
   ```
