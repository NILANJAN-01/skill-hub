---
name: git-objects
description: "Git internals: blob, tree and commit objects and the .git/objects store. Use when you need to inspect how git stores data."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git Objects"
  category: git-internals
  source: "Pro Git, 2nd edition"
  pages: "421-431"
---

# Git Objects

The next type of Git object we’ll examine is the tree, which solves the problem of storing the filename and also allows you to store a group of files together.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git cat-file -p`: `git cat-file -p fdf4fc3`
- `git write-tree`
- `git hash-object -w`: `git hash-object -w test.txt`
- `git cat-file -t`: `git cat-file -t 1f7a7a472abf3dd9643fd615f6da379c4acb3e3a`
- `git init`: `git init test`
- `git update-index --add --cacheinfo`: `git update-index --add --cacheinfo 100644 \`
- `git update-index --cacheinfo`: `git update-index --cacheinfo 100644 \`
- `git update-index --add`: `git update-index --add new.txt`
- `git read-tree --prefix`: `git read-tree --prefix=bak d8329fc1cc938780ffdd9f94e0d364e0ea74f579`
- `git log --stat`: `git log --stat 1a410e`
- `irb`

## Troubleshooting

- **Note:** In CMD on Windows, the `^` character is used for escaping, so you have to double it to avoid this: `git cat-file -p master^^{tree}`. When using PowerShell, parameters using `{}` characters have to be quoted to avoid the parameter being parsed incorrectly: `git cat-file -p 'master^{tree}'`.
- **Note:** You will get a different hash value because of different creation time and author data. Moreover, while in principle any commit object can be reproduced precisely given that data, historical details of this book’s construction mean that the printed commit hashes might not correspond to the given commits. Replace commit and tag hashes with your own checksums further in this chapter.

## Related skills

- `git-packfiles` - Packfiles
- `git-references` - Git References
- `git-branches-in-a-nutshell` - Branches in a Nutshell
- `git-reset-demystified` - Reset Demystified

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 421-431, CC BY-NC-SA 3.0._
