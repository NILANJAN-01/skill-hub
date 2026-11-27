---
name: git-rerere
description: "Reuse recorded merge conflict resolutions with git rerere. Use when resolving the same conflict repeatedly."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Rerere"
  category: git-branching
  source: "Pro Git, 2nd edition"
  pages: "294-301"
---

# Rerere

The `git rerere` functionality is a bit of a hidden feature.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git reset --hard HEAD^`
  - `git rebase master`
  - `git rebase --continue`

## Commands

- `git rerere`
- `git add`: `git add hello.rb`
- `git config --global`: `git config --global rerere.enabled true`
- `git merge`: `git merge i18n-world`
- `git status`
- `git ls-files -u`
- `git commit`
- `git reset --hard`: `git reset --hard HEAD^`
- `git checkout`: `git checkout i18n-world`
- `git rebase`: `git rebase master`
- `git diff`
- `git checkout --conflict`: `git checkout --conflict=merge hello.rb`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `CONFLICT (content): Merge conflict in hello.rb` | You should notice the new line `Recorded preimage for FILE` in there. |

## Related skills

- `git-advanced-merging` - Advanced Merging
- `git-rebasing` - Rebasing
- `git-basic-branching-and-merging` - Basic Branching and Merging
- `git-reset-demystified` - Reset Demystified

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 294-301, CC BY-NC-SA 3.0._
