# More procedures: Maintaining a Project

### Applying Patches from Email

**Goal:** If you receive a patch over email that you need to integrate into your project, you need to apply the patch in your topic branch to evaluate it.

**Steps:**

1. Assuming you saved the patch at `/tmp/patch-ruby-client.patch`, you can apply the patch like this:
   ```bash
   git apply /tmp/patch-ruby-client.patch
   ```
2. You can also use `git apply` to see if a patch applies cleanly before you try actually applying it — you can run `git apply --check` with the patch:
   ```bash
   git apply --check 0001-see-if-this-helps-the-gem.patch
   ```
   Expected output (excerpt):
   ```text
   error: patch failed: ticgit.gemspec:1
   error: ticgit.gemspec: patch does not apply
   ```
3. It looks something like this:
   ```text
   From 330090432754092d704da8e76ca5c05c198e71a8 Mon Sep 17 00:00:00 2001
   From: Jessica Smith <jessica@example.com>
   Date: Sun, 6 Apr 2008 10:17:23 -0700
   Subject: [PATCH 1/2] Add limit to log function
   Limit log functionality to the first 20
   ```
4. However, if someone uploaded a patch file generated via `git format-patch` to a ticketing system or something similar, you can save the file locally and then pass that file saved on your disk to `git am` to apply it:
   ```bash
   git am 0001-limit-log-function.patch
   ```
   Expected output (excerpt):
   ```text
   Applying: Add limit to log function
   ```
5. For example, if this patch was applied from the mbox example above, the commit generated would look something like this:
   ```bash
   git log --pretty=fuller -1
   ```
   Expected output (excerpt):
   ```text
   commit 6c5e70b984a60b3cecd395edd5b48a7575bf58e0
   Author:     Jessica Smith <jessica@example.com>
   AuthorDate: Sun Apr 6 10:17:23 2008 -0700
   Commit:     Scott Chacon <schacon@gmail.com>
   ```
6. In that case, the `git am` process will fail and ask you what you want to do:
   ```bash
   git am 0001-see-if-this-helps-the-gem.patch
   ```
   Expected output (excerpt):
   ```text
   Applying: See if this helps the gem
   error: patch failed: ticgit.gemspec:1
   error: ticgit.gemspec: patch does not apply
   Patch failed at 0001.
   ```
7. You solve this issue much the same way — edit the file to resolve the conflict, stage the new file, and then run `git am --resolved` to continue to the next patch:
   ```bash
   (fix the file)
   git add ticgit.gemspec
   git am --resolved
   ```
   Expected output (excerpt):
   ```text
   Applying: See if this helps the gem
   ```
8. If you do have that commit — if the patch was based on a public commit — then the `-3` option is generally much smarter about applying a conflicting patch:
   ```bash
   git am -3 0001-see-if-this-helps-the-gem.patch
   ```
   Expected output (excerpt):
   ```text
   Applying: See if this helps the gem
   error: patch failed: ticgit.gemspec:1
   ```
9. Run:
   ```text
   error: ticgit.gemspec: patch does not apply
   Using index info to reconstruct a base tree...
   Falling back to patching base and 3-way merge...
   No changes -- Patch already applied.
   ```
10. If you’re applying a number of patches from an mbox, you can also run the `am` command in interactive mode, which stops at each patch it finds and asks if you want to apply it:
   ```bash
   git am -3 -i mbox
   ```
   Expected output (excerpt):
   ```text
   Commit Body is:
   --------------------------
   See if this helps the gem
   --------------------------
   ```

**Verify:** run `git log --pretty=fuller -1` - expect something like:
```text
commit 6c5e70b984a60b3cecd395edd5b48a7575bf58e0
Author:     Jessica Smith <jessica@example.com>
AuthorDate: Sun Apr 6 10:17:23 2008 -0700
Commit:     Scott Chacon <schacon@gmail.com>
CommitDate: Thu Apr 9 09:19:06 2009 -0700
   Add limit to log function
```

**If it fails:** Finally, `git apply` is an “apply all or abort all” model where either everything is applied or nothing is, whereas `patch` can partially apply patchfiles, leaving your working directory in a weird state.

### Determining What Is Introduced

**Goal:** Determining What Is Introduced

**Steps:**

1. For example, if your contributor sends you two patches and you create a branch called `contrib` and applied those patches there, you can run this:
   ```bash
   git log contrib --not master
   ```
   Expected output (excerpt):
   ```text
   commit 5b6235bd297351589efc4d73316f0a68d484f118
   Author: Scott Chacon <schacon@gmail.com>
   Date:   Fri Oct 24 09:53:59 2008 -0700
       See if this helps the gem
   ```
2. You may think to run this:
   ```bash
   git diff master
   ```
3. Technically, you can do that by explicitly figuring out the common ancestor and then running your diff on it:
   ```bash
   git merge-base contrib master
   git diff 36c7db
   ```
   Expected output (excerpt):
   ```text
   36c7dba2c95e6bbb78dfa822519ecfec6e1ca649
   ```
4. or, more concisely:
   ```bash
   git diff $(git merge-base contrib master)
   ```
5. In the context of the `git diff` command, you can put three periods after another branch to do a `diff` between the last commit of the branch you’re on and its common ancestor with another branch:
   ```bash
   git diff master...contrib
   ```

**Verify:** run `git diff master...contrib`

### Integrating Contributed Work

**Goal:** This way, when people clone your project’s repository, they can either check out `master` to build the latest stable version and keep up to date on that easily, or they can check out `develop`, which is the more cutting-edge content.

**Steps:**

1. If you want to pull commit `e43a6` into your `master` branch, you can run:
   ```bash
   git cherry-pick e43a6
   ```
   Expected output (excerpt):
   ```text
   Finished one cherry-pick.
   [master]: created a0a41a9: "More friendly message when locking the index fails."
    3 files changed, 17 insertions(+), 3 deletions(-)
   ```
2. The configuration setting is `rerere.enabled`, and it’s handy enough to put in your global config:
   ```bash
   git config --global rerere.enabled true
   ```

**If it fails:** When rerere is enabled, Git will keep a set of pre- and post-images from successful merges, and if it notices that there’s a conflict that looks exactly like one you’ve already fixed, it’ll just use the fix from last time, without bothering you with it.

### Generating a Build Number

**Goal:** Generating a Build Number

**Steps:**

1. Git):
   ```bash
   git describe master
   ```
   Expected output (excerpt):
   ```text
   v1.6.2-rc1-20-g8c5b85c
   ```

### The Shortlog

**Goal:** It’s time to email your mailing list of people who want to know what’s happening in your project.

**Steps:**

1. It summarizes all the commits in the range you give it; for example, the following gives you a summary of all the commits since your last release, if your last release was named `v1.0.1`:
   ```bash
   git shortlog --no-merges master --not v1.0.1
   ```
   Expected output (excerpt):
   ```text
   Chris Wanstrath (6):
         Add support for annotated tags to Grit::Tag
         Add packed-refs annotated tag support.
         Add Grit::Commit#to_patch
   ```
