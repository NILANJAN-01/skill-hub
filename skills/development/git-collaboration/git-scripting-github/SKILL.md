---
name: git-scripting-github
description: "Automate GitHub with webhooks, the REST API and Octokit. Use when you need to script GitHub or react to push and PR events."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Scripting GitHub"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "214-223"
---

# Scripting GitHub

The Hooks and Services section of GitHub repository administration is the easiest way to have

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `curl`: `curl https://api.github.com/users/schacon`
- `curl -H -H`: `curl -H "Content-Type: application/json" \`

## Related skills

- `git-github-contributing-to-a-project` - Contributing to a Project
- `git-github-maintaining-a-project` - Maintaining a Project
- `git-hooks` - Git Hooks
- `git-libgit2` - Libgit2

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 214-223, CC BY-NC-SA 3.0._
