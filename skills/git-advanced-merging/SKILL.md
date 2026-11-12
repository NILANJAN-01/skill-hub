---
name: git-advanced-merging
description: "Resolve hard merge conflicts: abort or redo a merge, ignore whitespace, check out the ours/theirs/base versions, diff3 markers, undo a merge commit, subtree merges. Use when a git merge has conflicts or went wrong."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Advanced Merging"
  category: git-branching
  source: "Pro Git, 2nd edition"
  pages: "277-294"
---

# Advanced Merging

When you invoke a merge into `HEAD` (`git merge topic`), the new commit has two parents: the first one is `HEAD` (`C6`), and the second is the tip of the branch being merged in (`C4`).

_Built from "Pro Git" (pages 277-294) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **advanced merging** (git merge, merge conflict, merge commit, git diff, rack).
- The user wants to run or understand `git merge`.
- The user wants to run or understand `git merge --abort`.
- The user wants to run or understand `git merge -Xignore-space-change`.
- The user wants to run or understand `git merge-file -p`.
- The user sees an error like `CONFLICT (content): Merge conflict in hello.rb`.
- The user sees an error like `warning: no common commits`.
- If you want to get an idea before finalizing this commit about what was actually changed between one side or the other, you can ask `git diff` to compare what is in your working directory that you’re about to commit as the result of the merge to any of these stages.
- If you want to do something like this but not have Git even try to merge changes from the other side in, there is a more draconian option, which is the “ours” merge strategy.
- Another slightly weird thing is that to get a diff between what you have in your `rack` subdirectory and the code in your `rack_branch` branch — to see if you need to merge them — you can’t use the normal `diff` command.

## When NOT to use

- The new commit `^M` has exactly the same contents as `C6`, so starting from here it’s as if the merge never happened, except that the now-unmerged commits are still in `HEAD`’s history.
- For basic branching and merging, use the `git-basic-branching-and-merging` skill instead.
- For rerere, use the `git-rerere` skill instead.
- For contributing to a project, use the `git-distributed-git-contributing-to-a-project` skill instead.

## Key concepts

- By default, Git sees all of these lines as being changed, so it can’t merge the files.
- If we try to merge the `mundo` branch in, we get a conflict.
- We would like to see what the merge conflict is.
- If we add the `--merge` option to `git log`, it will only show the commits in either side of the merge that touch a file that’s currently conflicted.
- By default, when Git sees a conflict between two branches being merged, it will add merge conflict markers into your code and mark the file as conflicted and let you resolve it.
- If you want to do something like this but not have Git even try to merge changes from the other side in, there is a more draconian option, which is the “ours” merge strategy.
- This can often be useful to basically trick Git into thinking that a branch is already merged when doing a merge later on.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git clean -f`
- The downside of this approach is that it’s rewriting history, which can be problematic with a shared repository.
- This approach also won’t work if any other commits have been created since the merge; moving the refs would effectively lose those changes.

## Procedures

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

_25 more step(s) in references/procedures.md._

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

### Undoing Merges

**Goal:** When you invoke a merge into `HEAD` (`git merge topic`), the new commit has two parents: the first one is `HEAD` (`C6`), and the second is the tip of the branch being merged in (`C4`).

**Steps:**

1. Git calls this operation a “revert”, and in this particular scenario, you’d invoke it like this:
   ```bash
   git revert -m 1 HEAD
   ```
   Expected output (excerpt):
   ```text
   [master b1d8379] Revert "Merge branch 'topic'"
   ```
2. Git will get confused if you try to merge `topic` into `master` again:
   ```bash
   git merge topic
   ```
   Expected output (excerpt):
   ```text
   Already up-to-date.
   ```
3. The best way around this is to un-revert the original merge, since now you want to bring in the changes that were reverted out, then create a new merge commit:
   ```bash
   git revert ^M
   git merge topic
   ```
   Expected output (excerpt):
   ```text
   [master 09f0126] Revert "Revert "Merge branch 'topic'""
   ```

**If it fails:** One of the great things about working with Git is that it’s okay to make mistakes, because it’s possible (and in many cases easy) to fix them.

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

_5 more step(s) in references/procedures.md._

**Verify:** run `git diff-tree -p rack_remote/master`

**If it fails:** By default, when Git sees a conflict between two branches being merged, it will add merge conflict markers into your code and mark the file as conflicted and let you resolve it.

More procedures in [references/procedures.md](references/procedures.md):

- Merge Conflicts
- Other Types of Merges

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git merge` | When you invoke a merge into `HEAD` (`git merge topic`), the new commit has two parents: the first one is `HEAD` (`C6`), and the second is the tip of the branch being merged in (`C4`). | `git merge mundo` |
| `git checkout` | One helpful tool is `git checkout` with the `--conflict` option. | `git checkout master` |
| `git diff` | To compare your result to what you had in your branch before the merge, in other words, to see what the merge introduced, you can run `git diff --ours` | `git diff` |
| `git commit -am` | Then we change the line “hello world” to “hello mundo”. | `git commit -am 'Convert hello.rb to DOS'` |
| `git show` | You can extract a copy of each of these versions of the conflicted file with the `git show` command and a special syntax. | `git show :2:hello.rb > hello.ours.rb` |
| `git checkout -b` | Then we change the line “hello world” to “hello mundo”. | `git checkout -b whitespace` |
| `git diff -b` | Then we change the line “hello world” to “hello mundo”. | `git diff -b` |
| `git status -sb` | If you perhaps weren’t expecting conflicts and don’t want to quite deal with the situation yet, you can simply back out of the merge with `git merge --abort`. | `git status -sb` |
| `git log --oneline --left-right` | To get a full list of all of the unique commits that were included in either branch involved in this merge, we can use the “triple dot” syntax that we learned in Triple Dot. | `git log --oneline --left-right --merge` |
| `git diff-tree -p` | Instead, you must run `git diff-tree` with the branch you want to compare to | `git diff-tree -p rack_branch` |
| `unix2dos` | Then we change the line “hello world” to “hello mundo”. | `unix2dos hello.rb` |
| `git merge --abort` | The `git merge --abort` option tries to revert back to your state before you ran the merge. | `git merge --abort` |
| `git merge -Xignore-space-change` | The first option ignores whitespace completely when comparing lines, the second treats sequences of one or more whitespace characters as equivalent. | `git merge -Xignore-space-change whitespace` |
| `git ls-files -u` | If you want to get a little more hard core, you can also use the `ls-files -u` plumbing command to get the actual SHA-1s of the Git blobs for each of these files. | `git ls-files -u` |
| `dos2unix` | What we really need to do is run the file we’re trying to merge in through a `dos2unix` program before trying the actual file merge. | `dos2unix hello.theirs.rb` |
| `git merge-file -p` | Now that we have the content of all three stages in our working directory, we can manually fix up theirs to fix the whitespace issue and re-merge the file with the little-known `git merge-file` command which does just that. | `git merge-file -p \` |
| `git diff --ours` | To compare your result to what you had in your branch before the merge, in other words, to see what the merge introduced, you can run `git diff --ours` | `git diff --ours` |
| `git diff --theirs -b` | In this and the following example, we have to use `-b` to strip out the whitespace because we’re comparing it to what is in Git, not our cleaned up `hello.theirs.rb` file. | `git diff --theirs -b` |
| `git diff --base -b` | Finally, you can see how the file has changed from both sides with `git diff --base`. | `git diff --base -b` |
| `git clean -f` | At this point we can use the `git clean` command to clear out the extra files we created to do the manual merge but no longer need. | `git clean -f` |

## Decision guide

- In fact, this actually works better than the `ignore-space-change` option because this actually fixes the whitespace changes before merge instead of simply ignoring them.
- If you run that with the `-p` option instead, you get just the diffs to the file that ended up in conflict.
- If the unwanted merge commit only exists on your local repository, the easiest and best solution is to move the branches so that they point where you want them to.
- If you would prefer for Git to simply choose a specific side and ignore the other side instead of letting you manually resolve the conflict, you can pass the `merge` command either a `-Xours` or `-Xtheirs`.
- In that case, instead of getting conflict markers in the file with “hello mundo” on one side and “hola world” on the other, it will simply pick “hola world”.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `CONFLICT (content): Merge conflict in hello.rb` | First, let’s cover how to get out of this situation. |
| `warning: no common commits` | Now we have the root of the Rack project in our `rack_branch` branch and our own project in the `master` branch. |


## Related skills

- `git-basic-branching-and-merging` - Basic Branching and Merging
- `git-rerere` - Rerere
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-rebasing` - Rebasing

## Source

"Pro Git", pages 277-294. Sections: Advanced Merging; Advanced Merging > Merge Conflicts; Advanced Merging > Undoing Merges; Advanced Merging > Other Types of Merges.
