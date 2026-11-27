---
name: git-the-protocols
description: "Compare local, HTTP, SSH and git:// protocols for a repository. Use when you need to choose between HTTPS and SSH URLs."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "The Protocols"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "111-116"
---

# The Protocols

The most basic is the Local protocol, in which the remote repository is in another directory on the same host.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git clone`: `git clone /srv/git/project.git`
- `git remote`: `git remote add local_proj /srv/git/project.git`
- `git clone --bare`: `git clone --bare /path/to/git_project gitproject.git`
- `chmod`: `chmod a+x hooks/post-update`

## Related skills

- `git-transfer-protocols` - Transfer Protocols
- `git-getting-git-on-a-server` - Getting Git on a Server
- `git-daemon` - Git Daemon
- `git-getting-a-git-repository` - Getting a Git Repository

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 111-116, CC BY-NC-SA 3.0._
