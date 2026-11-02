# More procedures: Advanced Merging

### Merge Conflicts

**Goal:** Stage 1 is the common ancestor, stage 2 is your version and stage 3 is from the `MERGE_HEAD`, the version you’re merging in (“theirs”).

**Steps:**

1. We have a super simple Ruby file that prints 'hello world'.
   ```ruby
   #! /usr/bin/env ruby
   def hello
     puts 'hello world'
   end
   hello()
   ```
2. Then we change the line “hello world” to “hello mundo”.
   ```bash
   git checkout -b whitespace
   unix2dos hello.rb
   git commit -am 'Convert hello.rb to DOS'
   vim hello.rb
   git diff -b
   ```
   Expected output (excerpt):
   ```text
   Switched to a new branch 'whitespace'
   unix2dos: converting file hello.rb to DOS format ...
   [whitespace 3270f76] Convert hello.rb to DOS
    1 file changed, 7 insertions(+), 7 deletions(-)
   ```
3. Run:
   ```bash
   git commit -am 'Use Spanish instead of English'
   ```
   Expected output (excerpt):
   ```text
   [whitespace 6d338d2] Use Spanish instead of English
    1 file changed, 1 insertion(+), 1 deletion(-)
   ```
4. Now we switch back to our `master` branch and add some documentation for the function.
   ```bash
   git checkout master
   vim hello.rb
   git diff
   git commit -am 'Add comment documenting the function'
   ```
   Expected output (excerpt):
   ```text
   Switched to branch 'master'
   diff --git a/hello.rb b/hello.rb
   index ac51efd..36c06c8 100755
   --- a/hello.rb
   ```
5. Now we try to merge in our `whitespace` branch and we’ll get conflicts because of the whitespace changes.
   ```bash
   git merge whitespace
   ```
   Expected output (excerpt):
   ```text
   Auto-merging hello.rb
   CONFLICT (content): Merge conflict in hello.rb
   Automatic merge failed; fix conflicts and then commit the result.
   ```
6. If you perhaps weren’t expecting conflicts and don’t want to quite deal with the situation yet, you can simply back out of the merge with `git merge --abort`.
   ```bash
   git status -sb
   ```
   Expected output (excerpt):
   ```text
   ## master
   ```
7. Run:
   ```bash
   git merge --abort
   git status -sb
   ```
   Expected output (excerpt):
   ```text
   ## master
   ```
8. The first option ignores whitespace completely when comparing lines, the second treats sequences of one or more whitespace characters as equivalent.
   ```bash
   git merge -Xignore-space-change whitespace
   ```
   Expected output (excerpt):
   ```text
   Auto-merging hello.rb
   Merge made by the 'recursive' strategy.
    hello.rb | 2 +-
    1 file changed, 1 insertion(+), 1 deletion(-)
   ```
9. You can extract a copy of each of these versions of the conflicted file with the `git show` command and a special syntax.
   ```bash
   git show :1:hello.rb > hello.common.rb
   git show :2:hello.rb > hello.ours.rb
   git show :3:hello.rb > hello.theirs.rb
   ```
10. If you want to get a little more hard core, you can also use the `ls-files -u` plumbing command to get the actual SHA-1s of the Git blobs for each of these files.
   ```bash
   git ls-files -u
   ```
   Expected output (excerpt):
   ```text
   100755 ac51efdc3df4f4fd328d1a02ad05331d8e2c9111 1   hello.rb
   100755 36c06c8752c78d2aff89571132f3bf7841a7b5c3 2   hello.rb
   100755 e85207e04dfdd5eb0a1e9febbc67fd837c44a1cd 3   hello.rb
   ```
11. Now that we have the content of all three stages in our working directory, we can manually fix up theirs to fix the whitespace issue and re-merge the file with the little-known `git merge-file` command which does just that.
   ```bash
   dos2unix hello.theirs.rb
   git merge-file -p \
   hello.ours.rb hello.common.rb hello.theirs.rb > hello.rb
   git diff -b
   ```
   Expected output (excerpt):
   ```text
   dos2unix: converting file hello.theirs.rb to Unix format ...
   diff --cc hello.rb
   index 36c06c8,e85207e..0000000
   --- a/hello.rb
   ```
12. Run:
   ```ruby
     end
     hello()
   ```

_19 more step(s) in references/source-text.md._

**Verify:** run `git log --cc -p -1` - expect something like:
```text
commit 14f41939956d80b9e17bb8721354c33f8d5b5a79
Merge: f1270f7 e3eb223
Author: Scott Chacon <schacon@gmail.com>
Date:   Fri Sep 19 18:14:49 2014 +0200
    Merge branch 'mundo'
    Conflicts:
```

**If it fails:** This makes it so that you can undo anything you try here.

### Other Types of Merges

**Goal:** If you want to do something like this but not have Git even try to merge changes from the other side in, there is a more draconian option, which is the “ours” merge strategy.

**Steps:**

1. If we go back to the “hello world” example we were using before, we can see that merging in our branch causes conflicts.
   ```bash
   git merge mundo
   ```
   Expected output (excerpt):
   ```text
   Auto-merging hello.rb
   CONFLICT (content): Merge conflict in hello.rb
   Resolved 'hello.rb' using previous resolution.
   Automatic merge failed; fix conflicts and then commit the result.
   ```
2. However if we run it with `-Xours` or `-Xtheirs` it does not.
   ```bash
   git merge -Xours mundo
   ```
   Expected output (excerpt):
   ```text
   Auto-merging hello.rb
   ```
3. Run:
   ```text
   Merge made by the 'recursive' strategy.
    hello.rb | 2 +-
    test.sh  | 2 ++
    2 files changed, 3 insertions(+), 1 deletion(-)
    create mode 100644 test.sh
   ```
4. It will simply record as the result of the merge the exact code in your current branch.
   ```bash
   git merge -s ours mundo
   git diff HEAD HEAD~
   ```
   Expected output (excerpt):
   ```text
   Merge made by the 'ours' strategy.
   $
   ```
5. We’ll add the Rack project as a remote reference in our own project and then check it out into its own branch:
   ```bash
   git remote add rack_remote https://github.com/rack/rack
   git fetch rack_remote --no-tags
   git checkout -b rack_branch rack_remote/master
   ```
   Expected output (excerpt):
   ```text
   warning: no common commits
   remote: Counting objects: 3184, done.
   remote: Compressing objects: 100% (1465/1465), done.
   remote: Total 3184 (delta 1952), reused 2770 (delta 1675)
   ```
6. If you check out one and then the other, you can see that they have different project roots:
   ```bash
   ls
   git checkout master
   ls
   ```
   Expected output (excerpt):
   ```text
   AUTHORS         KNOWN-ISSUES   Rakefile      contrib         lib
   COPYING         README         bin           example         test
   Switched to branch "master"
   README
   ```
7. We just switched back to your `master` branch, and we pull the `rack_branch` branch into the `rack` subdirectory of our `master` branch of our main project:
   ```bash
   git read-tree --prefix=rack/ -u rack_branch
   ```
8. So, if the Rack project updates, we can pull in upstream changes by switching to that branch and pulling:
   ```bash
   git checkout rack_branch
   git pull
   ```
9. The recursive strategy is the default here, but we include it for clarity.
   ```bash
   git checkout master
   git merge --squash -s recursive -Xsubtree=rack rack_branch
   ```
   Expected output (excerpt):
   ```text
   Squash commit -- not updating HEAD
   Automatic merge went well; stopped before committing as requested
   ```
10. Instead, you must run `git diff-tree` with the branch you want to compare to:
   ```bash
   git diff-tree -p rack_branch
   ```
11. Or, to compare what is in your `rack` subdirectory with what the `master` branch on the server was the last time you fetched, you can run:
   ```bash
   git diff-tree -p rack_remote/master
   ```

**Verify:** run `git diff-tree -p rack_remote/master`

**If it fails:** By default, when Git sees a conflict between two branches being merged, it will add merge conflict markers into your code and mark the file as conflicted and let you resolve it.
