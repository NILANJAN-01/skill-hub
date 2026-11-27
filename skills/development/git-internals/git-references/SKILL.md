---
name: git-references
description: "Git refs internals: refs/heads, HEAD, update-ref, symbolic-ref. Use when asked what a ref is or to repair .git/refs."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git References"
  category: git-internals
  source: "Pro Git, 2nd edition"
  pages: "431-435"
---

# Git References

That’s basically what a branch in Git is: a simple pointer or reference to the head of a line of work.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git update-ref`: `git update-ref refs/heads/test cac0ca`
- `git symbolic-ref`: `git symbolic-ref HEAD`
- `git log --pretty`: `git log --pretty=oneline test`
- `git tag -a -m`: `git tag -a v1.1 1a410efbd13591db07496601ebc7a059dd55cfe9 -m 'Test tag'`
- `git cat-file -p`: `git cat-file -p 9585191f37f7b0fb9444f35a9bf50de191beadc2`
- `git cat-file`: `git cat-file blob junio-gpg-pub`
- `git remote`: `git remote add origin git@github.com:schacon/simplegit-progit.git`
- `git push`: `git push origin master`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `fatal: Refusing to point HEAD outside of refs/` | See references/source-text.md for this section. |

## Related skills

- `git-objects` - Git Objects
- `git-branches-in-a-nutshell` - Branches in a Nutshell
- `git-maintenance-and-data-recovery` - Maintenance and Data Recovery
- `git-reset-demystified` - Reset Demystified

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 431-435, CC BY-NC-SA 3.0._
