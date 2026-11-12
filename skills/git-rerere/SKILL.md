---
name: git-rerere
description: "Reuse recorded conflict resolutions with git rerere (rerere.enabled, git rerere status, git rerere diff). Use when the user keeps resolving the same merge or rebase conflicts."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Rerere"
  category: git-branching
  source: "Pro Git, 2nd edition"
  pages: "294-301"
---

# Rerere

The `git rerere` functionality is a bit of a hidden feature.

_Built from "Pro Git" (pages 294-301) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **rerere** (git rerere, merge conflict, topic branch, resolve, recorded).
- The user wants to run or understand `git rerere`.
- The user wants to run or understand `git add`.
- The user wants to run or understand `cat`.
- The user wants to run or understand `git config --global`.
- The user sees an error like `CONFLICT (content): Merge conflict in hello.rb`.

## When NOT to use

- For advanced merging, use the `git-advanced-merging` skill instead.
- For rebasing, use the `git-rebasing` skill instead.
- For basic branching and merging, use the `git-basic-branching-and-merging` skill instead.

## Key concepts

- The name stands for “reuse recorded resolution” and, as the name implies, it allows you to ask Git to remember how you’ve resolved a hunk conflict so that the next time it sees the same conflict, Git can resolve it for you automatically.
- With `rerere` enabled, you can attempt the occasional merge, resolve the conflicts, then back out of the merge.
- If you do this continuously, then the final merge should be easy because `rerere` can just do everything for you automatically.
- Or if you want to take a branch that you merged and fixed a bunch of conflicts and then decide to rebase it instead — you likely won’t have to do all the same conflicts again.
- Another application of `rerere` is where you merge a bunch of evolving topic branches together into a testable head occasionally, as the Git project itself often does.
- And `git rerere diff` will show the current state of the resolution — what you started with to resolve and what you’ve resolved it to.
- We have re-resolved the file automatically using the `rerere` cached resolution.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git reset --hard HEAD^`
  - `git rebase master`
  - `git rebase --continue`

## Procedures

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

_11 more step(s) in references/procedures.md._

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

More procedures in [references/procedures.md](references/procedures.md):

- Rerere

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git rerere` | The `git rerere` functionality is a bit of a hidden feature. | `git rerere` |
| `git add` | Now we can mark it as resolved and commit it | `git add hello.rb` |
| `git config --global` | To enable `rerere` functionality, you simply have to run this config setting | `git config --global rerere.enabled true` |
| `git merge` | When we merge the two branches together, we’ll get a merge conflict | `git merge i18n-world` |
| `git status` | Normally, you might run `git status` at this point to see what all conflicted | `git status` |
| `git ls-files -u` | Also (and this isn’t really related to `rerere`), you can use `git ls-files -u` to see the conflicted files and the before, left and right versions | `git ls-files -u` |
| `git commit` | Now we can mark it as resolved and commit it | `git commit` |
| `git reset --hard` | We can move our branch back by using `git reset` as we saw in Reset Demystified. | `git reset --hard HEAD^` |
| `git checkout` | You can also recreate the conflicted file state with `git checkout` | `git checkout i18n-world` |
| `git rebase` | Now let’s rebase the topic branch. | `git rebase master` |
| `git diff` | Also, `git diff` will show you how it was automatically re-resolved | `git diff` |
| `git checkout --conflict` | You can also recreate the conflicted file state with `git checkout` | `git checkout --conflict=merge hello.rb` |
| `git rebase --continue` | You can now add and continue the rebase to complete it. | `git rebase --continue` |

## Decision guide

- If you do this continuously, then the final merge should be easy because `rerere` can just do everything for you automatically.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `CONFLICT (content): Merge conflict in hello.rb` | You should notice the new line `Recorded preimage for FILE` in there. |


## Related skills

- `git-advanced-merging` - Advanced Merging
- `git-rebasing` - Rebasing
- `git-basic-branching-and-merging` - Basic Branching and Merging
- `git-reset-demystified` - Reset Demystified

## Source

"Pro Git", pages 294-301. Sections: Rerere.
