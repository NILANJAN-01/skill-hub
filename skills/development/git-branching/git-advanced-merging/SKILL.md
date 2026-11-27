---
name: git-advanced-merging
description: "Fix hard git merge conflicts: abort, redo, ours/theirs, undo a merge. Use when a merge has conflicts or went wrong."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Advanced Merging"
  category: git-branching
  source: "Pro Git, 2nd edition"
  pages: "277-294"
---

# Advanced Merging

When you invoke a merge into `HEAD` (`git merge topic`), the new commit has two parents: the first one is `HEAD` (`C6`), and the second is the tip of the branch being merged in (`C4`).

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git clean -f`
- The downside of this approach is that it’s rewriting history, which can be problematic with a shared repository.
- This approach also won’t work if any other commits have been created since the merge; moving the refs would effectively lose those changes.

## Commands

- `git merge`: `git merge mundo`
- `git checkout`: `git checkout master`
- `git diff`
- `git commit -am`: `git commit -am 'Convert hello.rb to DOS'`
- `git show`: `git show :2:hello.rb > hello.ours.rb`
- `git checkout -b`: `git checkout -b whitespace`
- `git diff -b`
- `git status -sb`
- `git log --oneline --left-right`: `git log --oneline --left-right --merge`
- `git diff-tree -p`: `git diff-tree -p rack_branch`
- `unix2dos`: `unix2dos hello.rb`
- `git merge --abort`

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

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 277-294, CC BY-NC-SA 3.0._
