---
name: git-revision-selection
description: "Pick commits and ranges: SHA, HEAD~2, HEAD^, .., ..., @{n}. Use when asked what ^, ~ or .. mean."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Revision Selection"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "224-232"
---

# Revision Selection

The last major range-selection syntax is the triple-dot syntax, which specifies all the commits that are reachable by either of two references but not by both of them.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git show`: `git show HEAD^`
- `git log`
- `git log --not`: `git log refB --not refA`
- `git log --abbrev-commit --pretty`: `git log --abbrev-commit --pretty=oneline`
- `git rev-parse`: `git rev-parse topic1`
- `git reflog`
- `git log -g`: `git log -g master`
- `git log --pretty --graph`: `git log --pretty=format:'%h %s' --graph`
- `git log --left-right`: `git log --left-right master...experiment`

## Troubleshooting

- **Note:** If you do happen to commit an object that hashes to the same SHA-1 value as a previous different object in your repository, Git will see the previous object already in your Git database, assume it was already written and simply reuse it. If you try to check out that object again at some point, you’ll always get the data of the first object.
- **Tip:** Think of the reflog as Git’s version of shell history If you have a UNIX or Linux background, you can think of the reflog as Git’s

## Related skills

- `git-references` - Git References
- `git-viewing-the-commit-history` - Viewing the Commit History
- `git-as-a-client` - Git as a Client
- `git-branches-in-a-nutshell` - Branches in a Nutshell

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 224-232, CC BY-NC-SA 3.0._
