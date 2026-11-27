---
name: git-credential-storage
description: "Stop git asking for passwords: credential helpers and Git Credential Manager. Use when git prompts on every push or pull."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Credential Storage"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "336-341"
---

# Credential Storage

This means that until you change your password for the Git host, you won’t ever have to type in your credentials again.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git config --global --file`: `git config --global credential.helper 'store --file ~/.my-credentials'`
- `git credential`: `git credential fill ①`
- `git credential-store --file`: `git credential-store --file ~/git.store get ②`
- `git config --global`: `git config --global credential.helper cache`
- `git credential-read-only --file`: `git credential-read-only --file=/mnt/shared/creds get`

## Related skills

- `git-configuration` - Git Configuration
- `git-the-protocols` - The Protocols
- `git-objects` - Git Objects
- `git-environment-variables` - Environment Variables

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 336-341, CC BY-NC-SA 3.0._
