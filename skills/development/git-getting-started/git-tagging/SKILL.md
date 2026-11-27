---
name: git-tagging
description: "Create, list, push and delete git tags. Use when you need to tag a commit or mark a release version."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Tagging"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "61-66"
---

# Tagging

The `-m` specifies a tagging message, which is stored with the tag.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git push origin :refs/tags/v1.4-lw`
  - `git push origin --delete <tagname>`

## Commands

- `git tag`
- `git show`: `git show v1.4`
- `git push`: `git push origin v1.5`
- `git checkout`: `git checkout v2.0.0`
- `git tag -l`: `git tag -l "v1.8.5*"`
- `git tag -a -m`: `git tag -a v1.4 -m "my version 1.4"`
- `git log --pretty`: `git log --pretty=oneline`
- `git tag -a`: `git tag -a v1.2 9fceb02`
- `git push --tags`: `git push origin --tags`
- `git tag -d`: `git tag -d v1.4-lw`
- `git push --delete`: `git push origin --delete <tagname>`
- `git checkout -b`: `git checkout -b version2 v2.0.0`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `You are in 'detached HEAD' state. You can look around, make experimental` | Thus, if you need to make changes — say you’re fixing a bug on an older version, for instance — you will generally want to create a branch: |

- **Note:** Listing tag wildcards requires `-l` or `--list` option If you want just the entire list of tags, running the command `git tag` implicitly assumes you want a listing and provides one; the use of `-l` or `--list` in this case is optional.
- **Note:** `git push` pushes both types of tags `git push <remote> --tags` will push both lightweight and annotated tags. There is currently no option to push only lightweight tags, but if you use `git push <remote>--follow-tags` only annotated tags will be pushed to the remote.

## Related skills

- `git-references` - Git References
- `git-signing-your-work` - Signing Your Work
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-remote-branches` - Remote Branches

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 61-66, CC BY-NC-SA 3.0._
