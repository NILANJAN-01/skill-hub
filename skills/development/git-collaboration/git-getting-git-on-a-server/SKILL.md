---
name: git-getting-git-on-a-server
description: "Host a git repository on your own server: bare repo over SSH. Use when you need to self-host a repository."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Getting Git on a Server"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "116-118"
---

# Getting Git on a Server

However, keep in mind that to collaborate with a couple of people on a private project, all you need is an SSH server and a bare repository.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- Note that by running this command, you will not destroy any commits, refs, etc. in the process.

## Commands

- `git clone --bare`: `git clone --bare my_project my_project.git`
- `scp -r`: `scp -r my_project.git user@git.example.com:/srv/git`
- `git clone`: `git clone user@git.example.com:/srv/git/my_project.git`
- `ssh`: `ssh user@git.example.com`
- `git init --bare --shared`

## Troubleshooting

- **Note:** Here we’ll be demonstrating the commands and steps needed to do basic, simplified installations on a Linux-based server, though it’s also possible to run these services on macOS or Windows servers. Actually setting up a production server within your infrastructure will certainly entail differences in security measures or operating system tools, but hopefully this will give you the general idea of what’s involved.

## Related skills

- `git-the-protocols` - The Protocols
- `git-getting-a-git-repository` - Getting a Git Repository
- `git-setting-up-the-server` - Setting Up the Server
- `git-daemon` - Git Daemon

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 116-118, CC BY-NC-SA 3.0._
