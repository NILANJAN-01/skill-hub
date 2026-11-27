---
name: git-gitweb
description: "Browse a git repository in a web browser with GitWeb or git instaweb. Use when handling a simple web viewer."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "GitWeb"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "125-127"
---

# GitWeb

Git comes with a CGI script called GitWeb that is sometimes used for this.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git instaweb --httpd`: `git instaweb --httpd=webrick`
- `git instaweb --httpd --stop`: `git instaweb --httpd=webrick --stop`
- `git clone`: `git clone https://git.kernel.org/pub/scm/git/git.git`
- `make`: `make GITWEB_PROJECTROOT="/srv/git" prefix=/usr gitweb`

## Related skills

- `git-smart-http` - Smart HTTP
- `git-installing-git` - Installing Git
- `git-getting-git-on-a-server` - Getting Git on a Server
- `git-setting-up-the-server` - Setting Up the Server

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 125-127, CC BY-NC-SA 3.0._
