# More procedures: Basic Branching and Merging

### Basic Branching

**Goal:** To phrase that another way, when you try to merge one commit with a commit that can be reached by following the first commit’s history, Git simplifies things by moving the pointer forward because there is no divergent work to merge together — this is called a “fast-forward.”

**Steps:**

1. To create a new branch and switch to it at the same time, you can run the `gitcheckout` command with the `-b` switch:
   ```bash
   git checkout -b iss53
   ```
   Expected output (excerpt):
   ```text
   Switched to a new branch "iss53"
   ```
2. This is shorthand for:
   ```bash
   git branch iss53
   git checkout iss53
   ```
3. Doing so moves the `iss53` branch forward, because you have it checked out (that is, your `HEAD` is pointing to it):
   ```bash
   vim index.html
   git commit -a -m 'Create new footer [issue 53]'
   ```
4. For now, let’s assume you’ve committed all your changes, so you can switch back to your `master` branch:
   ```bash
   git checkout master
   ```
   Expected output (excerpt):
   ```text
   Switched to branch 'master'
   ```
5. Let’s create a `hotfix` branch on which to work until it’s completed:
   ```bash
   git checkout -b hotfix
   vim index.html
   git commit -a -m 'Fix broken email address'
   ```
   Expected output (excerpt):
   ```text
   Switched to a new branch 'hotfix'
   [hotfix 1fb7853] Fix broken email address
    1 file changed, 2 insertions(+)
   ```
6. You do this with the `git merge` command:
   ```bash
   git checkout master
   git merge hotfix
   ```
   Expected output (excerpt):
   ```text
   Updating f42c576..3a0874c
   Fast-forward
    index.html | 2 ++
    1 file changed, 2 insertions(+)
   ```
7. You can delete it with the `-d` option to `gitbranch`:
   ```bash
   git branch -d hotfix
   ```
   Expected output (excerpt):
   ```text
   Deleted branch hotfix (3a0874c).
   ```
8. Now you can switch back to your work-in-progress branch on issue #53 and continue working on it.
   ```bash
   git checkout iss53
   vim index.html
   git commit -a -m 'Finish the new footer [issue 53]'
   ```
   Expected output (excerpt):
   ```text
   Switched to branch "iss53"
   [iss53 ad82d7a] Finish the new footer [issue 53]
   1 file changed, 1 insertion(+)
   ```

**If it fails:** Now you get the call that there is an issue with the website, and you need to fix it immediately.

### Basic Merge Conflicts

**Goal:** This means the version in `HEAD` (your `master` branch, because that was what you had checked out when you ran your merge command) is the top part of that block (everything above the `=======`), while the version in your `iss53` branch looks like everything in the bottom part.

**Steps:**

1. If your fix for issue #53 modified the same part of a file as the `hotfix` branch, you’ll get a merge conflict that looks something like this:
   ```bash
   git merge iss53
   ```
   Expected output (excerpt):
   ```text
   Auto-merging index.html
   CONFLICT (content): Merge conflict in index.html
   Automatic merge failed; fix conflicts and then commit the result.
   ```
2. If you want to see which files are unmerged at any point after a merge conflict, you can run `git status`:
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   You have unmerged paths.
     (fix conflicts and run "git commit")
   Unmerged paths:
   ```
3. Your file contains a section that looks something like this:
   ```text
   <<<<<<< HEAD:index.html
   <div id="footer">contact : email.support@github.com</div>
   =======
   <div id="footer">
    please contact us at support@github.com
   </div>
   >>>>>>> iss53:index.html
   ```
4. For instance, you might resolve this conflict by replacing the entire block with this:
   ```text
   <div id="footer">
   please contact us at email.support@github.com
   </div>
   ```
5. If you want to use a graphical tool to resolve these issues, you can run `git mergetool`, which fires up an appropriate visual merge tool and walks you through the conflicts:
   ```bash
   git mergetool
   ```
   Expected output (excerpt):
   ```text
   This message is displayed because 'merge.tool' is not configured.
   See 'git mergetool --tool-help' or 'git help config' for more details.
   'git mergetool' will now attempt to use one of the following tools:
   opendiff kdiff3 tkdiff xxdiff meld tortoisemerge gvimdiff diffuse diffmerge ecmerge
   ```
6. You can run `git status` again to verify that all conflicts have been resolved:
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   All conflicts fixed but you are still merging.
     (use "git commit" to conclude merge)
   Changes to be committed:
   ```
7. The commit message by default looks something like this:
   ```text
   Merge branch 'iss53'
   Conflicts:
   ```
8. Run:
   ```text
       index.html
   #
   # It looks like you may be committing a merge.
   # If this is not correct, please remove the file
   #   .git/MERGE_HEAD
   # and try again.
   # Please enter the commit message for your changes. Lines starting
   # with '#' will be ignored, and an empty message aborts the commit.
   # On branch master
   # All conflicts fixed but you are still merging.
   #
   # Changes to be committed:
   #   modified:   index.html
   #
   ```

**Verify:** run `git status` - expect something like:
```text
On branch master
All conflicts fixed but you are still merging.
  (use "git commit" to conclude merge)
Changes to be committed:
    modified:   index.html
```

**If it fails:** If your fix for issue #53 modified the same part of a file as the `hotfix` branch, you’ll get a merge conflict that looks something like this:
