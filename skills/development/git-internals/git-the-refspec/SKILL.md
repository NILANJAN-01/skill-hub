---
name: git-the-refspec
description: "Git refspecs: custom fetch and push mappings (+src:dst). Use when editing remote.<name>.fetch or mapping refs."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "The Refspec"
  category: git-internals
  source: "Pro Git, 2nd edition"
  pages: "438-441"
---

# The Refspec

Because the refspec is `<src>:<dst>`, by leaving off the `<src>` part, this basically says to make the `topic` branch on the remote nothing, which deletes it.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git push origin :topic`
  - `git push origin --delete topic`

## Commands

- `git log`: `git log origin/master`
- `git fetch`: `git fetch origin master:refs/remotes/origin/mymaster`
- `git push`: `git push origin :topic`
- `git remote`: `git remote add origin https://github.com/schacon/simplegit-progit`
- `git push --delete`: `git push origin --delete topic`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `! [rejected]        master     -> origin/mymaster  (non fast forward)` | In this case, the `master` branch pull was rejected because it wasn’t listed as a fast-forward reference. |

- **Note:** You cannot use the refspec to fetch from one repository and push to another one. For an example to do so, refer to Keep your GitHub public repository up-to-date.

## Related skills

- `git-remote-branches` - Remote Branches
- `git-working-with-remotes` - Working with Remotes
- `git-references` - Git References
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 438-441, CC BY-NC-SA 3.0._
