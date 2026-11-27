---
name: git-daemon
description: "Serve git repositories read-only over git:// with git daemon. Use when handling fast public read access."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git Daemon"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "122-123"
---

# Git Daemon

The `--reuseaddr` option allows the server to restart without waiting for old connections to time out, while the `--base-path` option allows people to clone projects without specifying the entire path, and the path at the end tells the Git daemon where to look for repositories to export.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git daemon --reuseaddr --base-path`: `git daemon --reuseaddr --base-path=/srv/git/ /srv/git/`

## Related skills

- `git-the-protocols` - The Protocols
- `git-getting-git-on-a-server` - Getting Git on a Server
- `git-smart-http` - Smart HTTP
- `git-setting-up-the-server` - Setting Up the Server

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 122-123, CC BY-NC-SA 3.0._
