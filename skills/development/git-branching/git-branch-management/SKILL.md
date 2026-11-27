---
name: git-branch-management
description: "List, rename and delete git branches; find merged or unmerged ones; rename master to main. Use when you need to clean up branches."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Branch Management"
  category: git-branching
  source: "Pro Git, 2nd edition"
  pages: "85-88"
---

# Branch Management

This means that if you commit at this point, the `master` branch will be moved forward with your new work.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git push origin --delete bad-branch-name`
  - `git push origin --delete master`
- **Caution (from source):** Do not rename branches that are still in use by other collaborators. Do not rename a branch like master/main/mainline without having read the section Changing the master branch name.
- **Warning (from source):** Changing the name of a branch like master/main/mainline/default will break the integrations, services, helper utilities and build/release scripts that your repository uses. Before you do this, make sure you consult with your collaborators. Also, make sure you do a thorough search through your repo and update any references to the old branch name in your code and scripts.
- Branches on this list without the `*` in front of them are generally fine to delete with `git branch -d`; you’ve already incorporated their work into another branch, so you’re not going to lose anything.

## Commands

- `git branch --no-merged`
- `git branch --move`: `git branch --move master main`
- `git push --set-upstream`: `git push --set-upstream origin main`
- `git branch --all`
- `git push --delete`: `git push origin --delete master`
- `git branch`
- `git branch -v`
- `git branch --merged`
- `git branch -d`: `git branch -d testing`
- `git checkout`: `git checkout testing`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error: The branch 'testing' is not fully merged.` | If you really do want to delete the branch and lose that work, you can force it with `-D`, as the helpful message points out. |

- **Tip:** You can always provide an additional argument to ask about the merge state with respect to some other branch without checking that other branch out first, as in, what is not merged into the `master` branch?

## Related skills

- `git-remote-branches` - Remote Branches
- `git-working-with-remotes` - Working with Remotes
- `git-basic-branching-and-merging` - Basic Branching and Merging
- `git-branches-in-a-nutshell` - Branches in a Nutshell

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 85-88, CC BY-NC-SA 3.0._
