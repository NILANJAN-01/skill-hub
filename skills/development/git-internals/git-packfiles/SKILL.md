---
name: git-packfiles
description: "How git packs objects: loose vs packfiles, delta compression, git gc. Use when asked why .git is large or what .pack files are."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Packfiles"
  category: git-internals
  source: "Pro Git, 2nd edition"
  pages: "435-438"
---

# Packfiles

The packfile is a single file containing the contents of all the objects that were removed from your filesystem.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git cat-file -p`: `git cat-file -p master^{tree}`
- `git cat-file -s`: `git cat-file -s 033b4468fa6b2a9547a70d88d1bbe8bf3f9ed0d5`
- `curl`: `curl https://raw.githubusercontent.com/mojombo/grit/master/lib/grit/repo.rb >`
- `git checkout`: `git checkout master`
- `git add`: `git add repo.rb`
- `git commit -m`: `git commit -m 'Create repo.rb'`
- `git commit -am`: `git commit -am 'Modify repo.rb a bit'`
- `git gc`
- `git verify-pack -v`: `git verify-pack -v .git/objects/pack/pack-`

## Related skills

- `git-objects` - Git Objects
- `git-maintenance-and-data-recovery` - Maintenance and Data Recovery
- `git-references` - Git References
- `git-branches-in-a-nutshell` - Branches in a Nutshell

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 435-438, CC BY-NC-SA 3.0._
