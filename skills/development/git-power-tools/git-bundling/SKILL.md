---
name: git-bundling
description: "Move git history in one file with git bundle, no network. Use when you need to share a repository offline."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Bundling"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "324-328"
---

# Bundling

The first command is the `bundle verify` command that will make sure the file is actually a valid Git bundle and that you have all the necessary ancestors to reconstitute it properly.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git bundle`: `git bundle verify ../commits.bundle`
- `git log --oneline`
- `git log`
- `git clone`: `git clone repo.bundle repo`
- `git fetch`: `git fetch ../commits.bundle master:other-master`
- `git log --oneline --decorate`: `git log --oneline --decorate --graph --all`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error: Repository lacks these prerequisite commits:` | However, our first bundle is valid, so we can fetch in commits from it. |

## Related skills

- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-working-with-remotes` - Working with Remotes
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-remote-branches` - Remote Branches

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 324-328, CC BY-NC-SA 3.0._
