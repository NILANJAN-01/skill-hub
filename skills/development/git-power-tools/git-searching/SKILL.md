---
name: git-searching
description: "Search code and history: git grep, log -S, log -G, log -L. Use when you need to find where something is or when it changed."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Searching"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "245-249"
---

# Searching

Another fairly advanced log search that is insanely useful is the line history search.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git grep -n`: `git grep -n gmtime_r`
- `git grep --count`: `git grep --count gmtime_r`
- `git grep -p`: `git grep -p gmtime_r *.c`
- `git grep --break --heading`: `git grep --break --heading \`
- `git log -S --oneline`: `git log -S ZLIB_BUF_MAX --oneline`
- `git log -L`: `git log -L :git_deflate_bound:zlib.c`

## Related skills

- `git-viewing-the-commit-history` - Viewing the Commit History
- `git-debugging-with-git` - Debugging with Git
- `git-migrating-to-git` - Migrating to Git
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 245-249, CC BY-NC-SA 3.0._
