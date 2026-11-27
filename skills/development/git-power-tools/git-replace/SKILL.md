---
name: git-replace
description: "Swap one git object for another with git replace to graft history. Use when you need to join or split history without rewriting it."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Replace"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "328-336"
---

# Replace

The `replace` command lets you specify an object in Git and say "every time you refer to this object, pretend it’s a different object".

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git rebase --onto 622e88 9c68fdc`

## Commands

- `git log --oneline`
- `git log --oneline --decorate`
- `git remote`: `git remote add project-history https://github.com/schacon/project-history`
- `git branch`: `git branch history c6e1e95`
- `git push`: `git push project-history history:master`
- `git rebase --onto`: `git rebase --onto 622e88 9c68fdc`
- `git clone`: `git clone https://github.com/schacon/project`
- `git fetch`: `git fetch project-history`
- `git replace`: `git replace 81a708d c6e1e95`
- `git cat-file -p`: `git cat-file -p 81a708d`
- `git for-each-ref`

## Troubleshooting

- **Note:** The `commit-tree` command is one of a set of commands that are commonly referred to as 'plumbing' commands. These are commands that are not generally meant to be used directly, but instead are used by other Git commands to do smaller jobs. On occasions when we’re doing weirder things like this, they allow us to do really low-level things but are not meant for daily use. You can read more about plumbing commands in Plumbing and Porcelain.

## Related skills

- `git-branches-in-a-nutshell` - Branches in a Nutshell
- `git-as-a-client` - Git as a Client
- `git-references` - Git References
- `git-objects` - Git Objects

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 328-336, CC BY-NC-SA 3.0._
