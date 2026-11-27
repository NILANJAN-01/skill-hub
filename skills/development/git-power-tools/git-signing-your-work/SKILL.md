---
name: git-signing-your-work
description: "Sign and verify git commits and tags with GPG. Use when you need to sign commits or tags."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Signing Your Work"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "242-245"
---

# Signing Your Work

If you’re taking work from others on the internet and want to verify that commits are actually from a trusted source, Git has a few ways to sign and verify work using GPG.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git merge --verify-signatures`: `git merge --verify-signatures non-verify`
- `gpg --list-keys`
- `gpg --gen-key`
- `git config --global`: `git config --global user.signingkey 0A46826A!`
- `git tag -s -m`: `git tag -s v1.5 -m 'my signed 1.5 tag'`
- `git show`: `git show v1.5`
- `git tag -v`: `git tag -v v1.4.2.1`
- `git commit -a -S`: `git commit -a -S -m 'Signed commit'`
- `git log --show-signature`: `git log --show-signature -1`
- `git log --pretty`: `git log --pretty="format:%h %G? %aN  %s"`
- `git merge --verify-signatures -S`: `git merge --verify-signatures -S  signed-branch`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error: could not verify the tag 'v1.4.2.1'` | See references/source-text.md for this section. |
| `fatal: Commit ab06180 does not have a GPG signature.` | If the merge contains only valid signed commits, the merge command will show you all the signatures it has checked and then move forward with the merge. |

## Related skills

- `git-tagging` - Tagging
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-configuration` - Git Configuration
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 242-245, CC BY-NC-SA 3.0._
