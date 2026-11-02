# More procedures: Recording Changes to the Repository

### Short Status

**Goal:** Git also has a short status flag so you can see your changes in a more compact way.

**Steps:**

1. If you run `git status -s` or `gitstatus --short` you get a far more simplified output from the command:
   ```bash
   git status -s
   ```
   Expected output (excerpt):
   ```text
    M README
   ```
2. Run:
   ```text
   MM Rakefile
   A  lib/git.rb
   M  lib/simplegit.rb
   ?? LICENSE.txt
   ```

### Ignoring Files

**Goal:** Setting up a `.gitignore` file for your new repository before you get going is generally a good idea so you don’t accidentally commit files that you really don’t want in your Git repository.

**Steps:**

1. Here is an example `.gitignore` file:
   ```bash
   cat .gitignore
   ```
   Expected output (excerpt):
   ```text
   *.[oa]
   *~
   ```
2. Here is another example `.gitignore` file:
   ```text
   # ignore all .a files
   *.a
   # but do track lib.a, even though you're ignoring .a files above
   !lib.a
   # only ignore the TODO file in the current directory, not subdir/TODO
   /TODO
   # ignore all files in any directory named build
   build/
   # ignore doc/notes.txt, but not doc/server/arch.txt
   doc/*.txt
   # ignore all .pdf files in the doc/ directory and any of its subdirectories
   doc/**/*.pdf
   ```

### Viewing Your Staged and Unstaged Changes

**Goal:** If the `git status` command is too vague for you — you want to know exactly what you changed, not just which files were changed — you can use the `git diff` command.

**Steps:**

1. If you run your `git status` command, you once again see something like this:
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   ```
2. Run:
   ```text
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
       modified:   README
   Changes not staged for commit:
     (use "git add <file>..." to update what will be committed)
     (use "git checkout -- <file>..." to discard changes in working directory)
       modified:   CONTRIBUTING.md
   ```
3. To see what you’ve changed but not yet staged, type `git diff` with no other arguments:
   ```bash
   git diff
   ```
   Expected output (excerpt):
   ```text
   diff --git a/CONTRIBUTING.md b/CONTRIBUTING.md
   index 8ebb991..643e24f 100644
   --- a/CONTRIBUTING.md
   +++ b/CONTRIBUTING.md
   ```
4. This command compares your staged changes to your last commit:
   ```bash
   git diff --staged
   ```
   Expected output (excerpt):
   ```text
   diff --git a/README b/README
   new file mode 100644
   index 0000000..03902a1
   --- /dev/null
   ```
5. If our environment looks like this:
   ```bash
   git add CONTRIBUTING.md
   echo '# test line' >> CONTRIBUTING.md
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
   ```
6. Now you can use `git diff` to see what is still unstaged:
   ```bash
   git diff
   ```
   Expected output (excerpt):
   ```text
   diff --git a/CONTRIBUTING.md b/CONTRIBUTING.md
   index 643e24f..87f08c8 100644
   --- a/CONTRIBUTING.md
   +++ b/CONTRIBUTING.md
   ```
7. and `git diff --cached` to see what you’ve staged so far (`--staged` and `--cached` are synonyms):
   ```bash
   git diff --cached
   ```
   Expected output (excerpt):
   ```text
   diff --git a/CONTRIBUTING.md b/CONTRIBUTING.md
   index 8ebb991..643e24f 100644
   --- a/CONTRIBUTING.md
   +++ b/CONTRIBUTING.md
   ```
8. Run:
   ```text
    If you are starting to work on a particular area, feel free to submit a PR
    that highlights your work in progress (and note in the PR title that it's
   ```

**Verify:** run `git diff --cached` - expect something like:
```text
diff --git a/CONTRIBUTING.md b/CONTRIBUTING.md
index 8ebb991..643e24f 100644
--- a/CONTRIBUTING.md
+++ b/CONTRIBUTING.md
@@ -65,7 +65,8 @@ branch directly, things can get messy.
 Please include a nice description of your changes when you submit your PR;
```

### Skipping the Staging Area

**Goal:** That’s because the `-a` flag includes all changed files.

**Steps:**

1. Git automatically stage every file that is already tracked before doing the commit, letting you skip the `git add` part:
   ```bash
   git status
   git commit -a -m 'Add new benchmarks'
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes not staged for commit:
     (use "git add <file>..." to update what will be committed)
   ```
2. Run:
   ```text
    1 file changed, 5 insertions(+), 0 deletions(-)
   ```

### Removing Files

**Goal:** This is a safety feature to prevent accidental removal of data that hasn’t yet been recorded in a snapshot and that can’t be recovered from Git.

**Steps:**

1. If you simply remove the file from your working directory, it shows up under the “Changes not staged for commit” (that is, unstaged) area of your `git status` output:
   ```bash
   rm PROJECTS.md
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes not staged for commit:
     (use "git add/rm <file>..." to update what will be committed)
   ```
2. Then, if you run `git rm`, it stages the file’s removal:
   ```bash
   git rm PROJECTS.md
   git status
   ```
   Expected output (excerpt):
   ```text
   rm 'PROJECTS.md'
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
   ```
3. To do this, use the `--cached` option:
   ```bash
   git rm --cached README
   ```
4. That means you can do things such as:
   ```bash
   git rm log/\*.log
   ```
5. Or, you can do something like this:
   ```bash
   git rm \*~
   ```

**If it fails:** This is a safety feature to prevent accidental removal of data that hasn’t yet been recorded in a snapshot and that can’t be recovered from Git.

### Moving Files

**Goal:** Moving Files

**Steps:**

1. If you want to rename a file in Git, you can run something like:
   ```bash
   git mv file_from file_to
   ```
2. In fact, if you run something like this and look at the status, you’ll see that Git considers it a renamed file:
   ```bash
   git mv README.md README
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
   ```
3. However, this is equivalent to running something like this:
   ```bash
   mv README.md README
   ```
4. Run:
   ```bash
   git rm README.md
   git add README
   ```
