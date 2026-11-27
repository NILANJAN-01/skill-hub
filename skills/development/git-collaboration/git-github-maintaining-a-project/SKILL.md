---
name: git-github-maintaining-a-project
description: "Maintain a GitHub repo: collaborators, merging pull requests, notifications, README. Use when administering a GitHub project."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Maintaining a Project"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "197-211"
---

# Maintaining a Project

Doing so will give them “push” access, which means they have both read and write access to the project and Git repository.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git fetch`
- `curl`: git am`
- `git ls-remote`: `git ls-remote https://github.com/schacon/blink`
- `git checkout`: `git checkout pr/2`

## Troubleshooting

- **Note:** It is often preferable to share the HTTPS based URL for a public project, since the user does not have to have a GitHub account to access it for cloning. Users will have to have an account and an uploaded SSH key to access your project if you give them the SSH URL. The HTTPS one is also exactly the same URL they would paste into a browser to view the project there.

## Related skills

- `git-github-contributing-to-a-project` - Contributing to a Project
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-scripting-github` - Scripting GitHub

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 197-211, CC BY-NC-SA 3.0._
