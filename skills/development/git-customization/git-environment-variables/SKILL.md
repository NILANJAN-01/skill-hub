---
name: git-environment-variables
description: "Git environment variables (GIT_DIR, GIT_EDITOR, GIT_SSH_COMMAND, GIT_TRACE). Use when handling a GIT_* variable or to trace git."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Environment Variables"
  category: git-customization
  source: "Pro Git, 2nd edition"
  pages: "453-458"
---

# Environment Variables

Some of Git’s general behavior as a computer program depends on environment variables.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- `GIT_FLUSH` can be used to force Git to use non-buffered I/O when writing incrementally to stdout.

## Commands

- `GIT_TRACE=true git`: `GIT_TRACE=true git lga`
- `GIT_TRACE_PACK_ACCESS=true git`: `GIT_TRACE_PACK_ACCESS=true git status`
- `GIT_TRACE_PACKET=true git`: `GIT_TRACE_PACKET=true git ls-remote origin`
- `GIT_TRACE_PERFORMANCE=true git`: `GIT_TRACE_PERFORMANCE=true git gc`
- `GIT_TRACE_SETUP=true git`: `GIT_TRACE_SETUP=true git status`
- `GIT_REFLOG_ACTION="my --allow-empty -m`: `GIT_REFLOG_ACTION="my action" git commit --allow-empty -m 'My message'`
- `git reflog`: `git reflog -1`

## Related skills

- `git-configuration` - Git Configuration
- `git-first-time-git-setup` - First-Time Git Setup
- `git-credential-storage` - Credential Storage
- `git-as-a-client` - Git as a Client

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 453-458, CC BY-NC-SA 3.0._
