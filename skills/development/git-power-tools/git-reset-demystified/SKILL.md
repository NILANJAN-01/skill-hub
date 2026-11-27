---
name: git-reset-demystified
description: "Explain git reset and checkout: --soft, --mixed, --hard and the three trees. Use when unsure which reset mode to use."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Reset Demystified"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "257-277"
---

# Reset Demystified

Like `reset`, `checkout` manipulates the three trees, and it is a bit different depending on whether you give the command a file path or not.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- It’s important to note that this flag (`--hard`) is the only way to make the `reset` command dangerous, and one of the very few cases where Git will actually destroy data.
- Any other invocation of `reset` can be pretty easily undone, but the `--hard` option cannot, since it forcibly overwrites files in the working directory.
- Git DB, and we could get it back by looking at our `reflog`, but if we had not committed it, Git still would have overwritten the file and it would be unrecoverable.
- It is just like `git reset [branch] file` in that it updates the index with that file at that commit, but it also overwrites the file in the working directory.

## Commands

- `git cat-file -p`: `git cat-file -p HEAD`
- `git ls-tree -r`: `git ls-tree -r HEAD`
- `git ls-files -s`

## Related skills

- `git-branches-in-a-nutshell` - Branches in a Nutshell
- `git-advanced-merging` - Advanced Merging
- `git-undoing-things` - Undoing Things
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 257-277, CC BY-NC-SA 3.0._
