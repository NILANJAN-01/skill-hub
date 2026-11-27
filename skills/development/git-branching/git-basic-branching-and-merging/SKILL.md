---
name: git-basic-branching-and-merging
description: "Create, switch, merge and delete a branch and resolve a basic conflict. Use when handling branch or merge tasks or CONFLICT (content)."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Basic Branching and Merging"
  category: git-branching
  source: "Pro Git, 2nd edition"
  pages: "76-85"
---

# Basic Branching and Merging

However, before you do that, note that if your working directory or staging area has uncommitted changes that conflict with the branch you’re checking out, Git won’t let you switch branches.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git checkout`: `git checkout iss53`
- `git commit -a -m`: `git commit -a -m 'Fix broken email address'`
- `git merge`: `git merge iss53`
- `git checkout -b`: `git checkout -b iss53`
- `git branch -d`: `git branch -d iss53`
- `git status`
- `git branch`: `git branch iss53`
- `git mergetool`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `CONFLICT (content): Merge conflict in index.html` | It has paused the process while you resolve the conflict. |

- **Note:** If you need more advanced tools for resolving tricky merge conflicts, we cover more on merging in Advanced Merging.

## Related skills

- `git-advanced-merging` - Advanced Merging
- `git-branches-in-a-nutshell` - Branches in a Nutshell
- `git-rebasing` - Rebasing
- `git-remote-branches` - Remote Branches

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 76-85, CC BY-NC-SA 3.0._
