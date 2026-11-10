# More procedures: Submodules

### Starting with Submodules

**Goal:** Although `DbConnector` is a subdirectory in your working directory, Git sees it as a submodule and doesn’t track its contents when you’re not in that directory.

**Steps:**

1. In this example, we’ll add a library called “DbConnector”.
   ```bash
   git submodule add https://github.com/chaconinc/DbConnector
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'DbConnector'...
   remote: Counting objects: 11, done.
   remote: Compressing objects: 100% (10/10), done.
   remote: Total 11 (delta 0), reused 11 (delta 0)
   ```
2. Run:
   ```text
   Unpacking objects: 100% (11/11), done.
   Checking connectivity... done.
   ```
3. If you run `git status` at this point, you’ll notice a few things.
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
   ```
4. This is a configuration file that stores the mapping between the project’s URL and the local subdirectory you’ve pulled it into:
   ```ini
   [submodule "DbConnector"]
       path = DbConnector
       url = https://github.com/chaconinc/DbConnector
   ```
5. If you run `git diff` on that, you see something interesting:
   ```bash
   git diff --cached DbConnector
   ```
   Expected output (excerpt):
   ```text
   diff --git a/DbConnector b/DbConnector
   new file mode 160000
   index 0000000..c3f01dc
   --- /dev/null
   ```
6. Run:
   ```text
   +++ b/DbConnector
   @@ -0,0 +1 @@
   +Subproject commit c3f01dc8862123d317dd46284b05b6892c7b29bc
   ```
7. If you want a little nicer diff output, you can pass the `--submodule` option to `git diff`.
   ```bash
   git diff --cached --submodule
   ```
   Expected output (excerpt):
   ```text
   diff --git a/.gitmodules b/.gitmodules
   new file mode 100644
   index 0000000..71fc376
   --- /dev/null
   ```
8. When you commit, you see something like this:
   ```bash
   git commit -am 'Add DbConnector module'
   ```
   Expected output (excerpt):
   ```text
   [master fb9093c] Add DbConnector module
    2 files changed, 4 insertions(+)
    create mode 100644 .gitmodules
    create mode 160000 DbConnector
   ```
9. Lastly, push these changes:
   ```bash
   git push origin master
   ```

**Verify:** run `git diff --cached --submodule` - expect something like:
```text
diff --git a/.gitmodules b/.gitmodules
new file mode 100644
index 0000000..71fc376
--- /dev/null
+++ b/.gitmodules
@@ -0,0 +1,3 @@
```

### Working on a Project with Submodules

**Goal:** If you want to check for new work in a submodule, you can go into the directory and run `git fetch` and `git merge` the upstream branch to update the local code.

**Steps:**

1. If you want to check for new work in a submodule, you can go into the directory and run `git fetch` and `git merge` the upstream branch to update the local code.
   ```bash
   git fetch
   git merge origin/master
   ```
   Expected output (excerpt):
   ```text
   From https://github.com/chaconinc/DbConnector
      c3f01dc..d0354fc  master     -> origin/master
   Updating c3f01dc..d0354fc
   Fast-forward
   ```
2. If you don’t want to type `--submodule` every time you run `git diff`, you can set it as the default format by setting the `diff.submodule` config value to “log”.
   ```bash
   git config --global diff.submodule log
   git diff
   ```
   Expected output (excerpt):
   ```text
   Submodule DbConnector c3f01dc..d0354fc:
   ```
3. Run:
   ```text
     > more efficient db routine
     > better connection routine
   ```
4. If you run `git submodule update --remote`, Git will go into your submodules and fetch and update for you.
   ```bash
   git submodule update --remote DbConnector
   ```
   Expected output (excerpt):
   ```text
   remote: Counting objects: 4, done.
   remote: Compressing objects: 100% (2/2), done.
   remote: Total 4 (delta 2), reused 4 (delta 2)
   Unpacking objects: 100% (4/4), done.
   ```
5. Let’s set it in the `.gitmodules` file:
   ```bash
   git config -f .gitmodules submodule.DbConnector.branch stable
   git submodule update --remote
   ```
   Expected output (excerpt):
   ```text
   remote: Counting objects: 4, done.
   remote: Compressing objects: 100% (2/2), done.
   remote: Total 4 (delta 2), reused 4 (delta 2)
   Unpacking objects: 100% (4/4), done.
   ```
6. When we run `git status` at this point, Git will show us that we have “new commits” on the submodule.
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes not staged for commit:
   ```
7. Run:
   ```text
     (use "git add <file>..." to update what will be committed)
     (use "git checkout -- <file>..." to discard changes in working directory)
     modified:   .gitmodules
     modified:   DbConnector (new commits)
   no changes added to commit (use "git add" and/or "git commit -a")
   ```
8. If you set the configuration setting `status.submodulesummary`, Git will also show you a short summary of changes to your submodules:
   ```bash
   git config status.submodulesummary 1
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes not staged for commit:
     (use "git add <file>..." to update what will be committed)
   ```
9. At this point if you run `git diff` we can see both that we have modified our `.gitmodules` file and also that there are a number of commits that we’ve pulled down and are ready to commit to our submodule project.
   ```bash
   git diff
   ```
   Expected output (excerpt):
   ```text
   diff --git a/.gitmodules b/.gitmodules
   index 6fc0b3d..fd1cc29 100644
   --- a/.gitmodules
   +++ b/.gitmodules
   ```
10. Once committed, you can see this information after the fact as well when you run `gitlog -p`.
   ```bash
   git log -p --submodule
   ```
   Expected output (excerpt):
   ```text
   commit 0a24cfc121a8a3c118e0105ae4ae4c00281cf7ae
   Author: Scott Chacon <schacon@gmail.com>
   Date:   Wed Sep 17 16:37:02 2014 +0200
       updating DbConnector for bug fixes
   ```
11. Simply executing `git pull` to get your newly committed changes is not enough:
   ```bash
   git pull
   git status
   ```
   Expected output (excerpt):
   ```text
   From https://github.com/chaconinc/MainProject
      fb9093c..0a24cfc  master     -> origin/master
   Fetching submodule DbConnector
   From https://github.com/chaconinc/DbConnector
   ```
12. Run:
   ```text
   Your branch is up-to-date with 'origin/master'.
   Changes not staged for commit:
     (use "git add <file>..." to update what will be committed)
     (use "git checkout -- <file>..." to discard changes in working directory)
       modified:   DbConnector (new commits)
   Submodules changed but not updated:
   * DbConnector c87d55d...c3f01dc (4):
     < catch non-null terminated lines
     < more robust error handling
     < more efficient db routine
     < better connection routine
   no changes added to commit (use "git add" and/or "git commit -a")
   ```

_20 more step(s) in references/source-text.md._

**Verify:** run `git diff` - expect something like:
```text
diff --cc DbConnector
index eb41d76,c771610..0000000
--- a/DbConnector
+++ b/DbConnector
```

**If it fails:** You can go into the submodule directory and fix the conflict just as you normally would.

### Issues with Submodules

**Goal:** For older Git versions that do not have the `--recurse-submodules` flag, after the checkout you can use `git submodule update --init --recursive` to put the submodules in the right state.

**Steps:**

1. If you create a new branch, add a submodule there, and then switch back to a branch without that submodule, you still have the submodule directory as an untracked directory:
   ```bash
   git --version
   git checkout -b add-crypto
   git submodule add https://github.com/chaconinc/CryptoLibrary
   git commit -am 'Add crypto library'
   ```
   Expected output (excerpt):
   ```text
   git version 2.12.2
   Switched to a new branch 'add-crypto'
   Cloning into 'CryptoLibrary'...
   ...
   ```
2. Run:
   ```bash
   git checkout master
   git status
   ```
   Expected output (excerpt):
   ```text
   warning: unable to rmdir CryptoLibrary: Directory not empty
   Switched to branch 'master'
   Your branch is up-to-date with 'origin/master'.
   On branch master
   ```
3. If you do remove it and then switch back to the branch that has that submodule, you will need to run `submodule update --init` to repopulate it.
   ```bash
   git clean -ffdx
   git checkout add-crypto
   ls CryptoLibrary/
   git submodule update --init
   ls CryptoLibrary/
   ```
   Expected output (excerpt):
   ```text
   Removing CryptoLibrary/
   Switched to branch 'add-crypto'
   Submodule path 'CryptoLibrary': checked out 'b8dda6aa182ea4464f3f3264b11e0268545172af'
   Makefile    includes    scripts     src
   ```
4. Newer Git versions (Git >= 2.13) simplify all this by adding the `--recurse-submodules` flag to the `gitcheckout` command, which takes care of placing the submodules in the right state for the branch we are switching to.
   ```bash
   git --version
   git checkout -b add-crypto
   git submodule add https://github.com/chaconinc/CryptoLibrary
   ```
   Expected output (excerpt):
   ```text
   git version 2.13.3
   Switched to a new branch 'add-crypto'
   ```
5. Run:
   ```bash
   git commit -am 'Add crypto library'
   git checkout --recurse-submodules master
   git status
   ```
   Expected output (excerpt):
   ```text
   [add-crypto 4445836] Add crypto library
    2 files changed, 4 insertions(+)
    create mode 160000 CryptoLibrary
   Switched to branch 'master'
   ```
6. If you delete the subdirectory and then run `submodule add`, Git yells at you:
   ```bash
   rm -Rf CryptoLibrary/
   git submodule add https://github.com/chaconinc/CryptoLibrary
   ```
   Expected output (excerpt):
   ```text
   'CryptoLibrary' already exists in the index
   ```
7. Then you can add the submodule:
   ```bash
   git rm -r CryptoLibrary
   git submodule add https://github.com/chaconinc/CryptoLibrary
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'CryptoLibrary'...
   remote: Counting objects: 11, done.
   remote: Compressing objects: 100% (10/10), done.
   remote: Total 11 (delta 0), reused 11 (delta 0)
   ```
8. If you try to switch back to a branch where those files are still in the actual tree rather than a submodule — you get this error:
   ```bash
   git checkout master
   ```
   Expected output (excerpt):
   ```text
   error: The following untracked working tree files would be overwritten by checkout:
     CryptoLibrary/Makefile
     CryptoLibrary/includes/crypto.h
     ...
   ```
9. You can force it to switch with `checkout -f`, but be careful that you don’t have unsaved changes in there as they could be overwritten with that command.
   ```bash
   git checkout -f master
   ```
   Expected output (excerpt):
   ```text
   warning: unable to rmdir CryptoLibrary: Directory not empty
   Switched to branch 'master'
   ```

**If it fails:** Then, when you switch back, you get an empty `CryptoLibrary` directory for some reason and `gitsubmodule update` may not fix it either.
