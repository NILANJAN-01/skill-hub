# More procedures: Stashing and Cleaning

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
7. To remove it, you can run `git stash drop` with the name of the stash to remove:
   ```bash
   git stash list
   git stash drop stash@{0}
   ```
   Expected output (excerpt):
   ```text
   stash@{0}: WIP on master: 049d078 Create index file
   stash@{1}: WIP on master: c264051 Revert "Add file_size"
   stash@{2}: WIP on master: 21d80a5 Add number to log
   Dropped stash@{0} (364e91f3f268f0900bc3ee613f9f733e82aaed43)
   ```

**Verify:** run `git stash list` - expect something like:
```text
stash@{0}: WIP on master: 049d078 Create index file
stash@{1}: WIP on master: c264051 Revert "Add file_size"
stash@{2}: WIP on master: 21d80a5 Add number to log
```

**If it fails:** You can see that Git re-modifies the files you reverted when you saved the stash.
