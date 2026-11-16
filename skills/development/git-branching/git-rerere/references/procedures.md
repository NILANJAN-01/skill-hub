# More procedures: Rerere

### Rerere

**Goal:** The `git rerere` functionality is a bit of a hidden feature.

**Steps:**

1. To enable `rerere` functionality, you simply have to run this config setting:
   ```bash
   git config --global rerere.enabled true
   ```
2. Let’s say we have a file named `hello.rb` that looks like this:
   ```ruby
   #! /usr/bin/env ruby
   def hello
     puts 'hello world'
   end
   ```
3. When we merge the two branches together, we’ll get a merge conflict:
   ```bash
   git merge i18n-world
   ```
   Expected output (excerpt):
   ```text
   Auto-merging hello.rb
   CONFLICT (content): Merge conflict in hello.rb
   Recorded preimage for 'hello.rb'
   Automatic merge failed; fix conflicts and then commit the result.
   ```
4. Normally, you might run `git status` at this point to see what all conflicted:
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   # On branch master
   # Unmerged paths:
   #   (use "git reset HEAD <file>..." to unstage)
   #   (use "git add <file>..." to mark resolution)
   ```
5. However, `git rerere` will also tell you what it has recorded the pre-merge state for with `git rererestatus`:
   ```bash
   git rerere status
   ```
   Expected output (excerpt):
   ```text
   hello.rb
   ```
6. And `git rerere diff` will show the current state of the resolution — what you started with to resolve and what you’ve resolved it to.
   ```bash
   git rerere diff
   ```
   Expected output (excerpt):
   ```text
   --- a/hello.rb
   +++ b/hello.rb
   @@ -1,11 +1,11 @@
    #! /usr/bin/env ruby
   ```
7. Also (and this isn’t really related to `rerere`), you can use `git ls-files -u` to see the conflicted files and the before, left and right versions:
   ```bash
   git ls-files -u
   ```
   Expected output (excerpt):
   ```text
   100644 39804c942a9c1f2c03dc7c5ebcd7f3e3a6b97519 1   hello.rb
   100644 a440db6e8d1fd76ad438a49025a9ad9ce746f581 2   hello.rb
   100644 54336ba847c3758ab604876419607e9443848474 3   hello.rb
   ```
8. Now you can resolve it to just be `puts 'hola mundo'` and you can run `git rerere diff` again to see what rerere will remember:
   ```bash
   git rerere diff
   ```
   Expected output (excerpt):
   ```text
   --- a/hello.rb
   +++ b/hello.rb
   @@ -1,11 +1,7 @@
    #! /usr/bin/env ruby
   ```
9. Now we can mark it as resolved and commit it:
   ```bash
   git add hello.rb
   git commit
   ```
   Expected output (excerpt):
   ```text
   Recorded resolution for 'hello.rb'.
   [master 68e16e5] Merge branch 'i18n'
   ```
10. Now, let’s undo that merge and then rebase it on top of our `master` branch instead.
   ```bash
   git reset --hard HEAD^
   ```
   Expected output (excerpt):
   ```text
   HEAD is now at ad63f15 i18n the hello
   ```
11. Now let’s rebase the topic branch.
   ```bash
   git checkout i18n-world
   git rebase master
   ```
   Expected output (excerpt):
   ```text
   Switched to branch 'i18n-world'
   First, rewinding head to replay your work on top of it...
   Applying: i18n one word
   Using index info to reconstruct a base tree...
   ```
12. Run:
   ```text
   Auto-merging hello.rb
   CONFLICT (content): Merge conflict in hello.rb
   Resolved 'hello.rb' using previous resolution.
   Failed to merge in the changes.
   Patch failed at 0001 i18n one word
   ```

_5 more step(s) in references/source-text.md._

**Verify:** run `git diff` - expect something like:
```text
diff --cc hello.rb
index a440db6,54336ba..0000000
--- a/hello.rb
+++ b/hello.rb
@@@ -1,7 -1,7 +1,7 @@@
  #! /usr/bin/env ruby
```

**If it fails:** The name stands for “reuse recorded resolution” and, as the name implies, it allows you to ask Git to remember how you’ve resolved a hunk conflict so that the next time it sees the same conflict, Git can resolve it for you automatically.
