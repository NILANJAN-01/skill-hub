---
name: git-setting-up-the-server
description: "Set up an SSH git server: git user, authorized_keys, bare repo, git-shell. Use when you need to self-host for several developers."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Setting Up the Server"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "119-122"
---

# Setting Up the Server

With this method, you can quickly get a read/write Git server up and running for a handful of developers.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git push`: `git push origin master`
- `adduser git`: `sudo adduser git`
- `su git`
- `git init --bare`
- `git init`
- `git add`: `git add .`
- `git commit -m`: `git commit -m 'Initial commit'`
- `git remote`: `git remote add origin git@gitserver:/srv/git/project.git`
- `git clone`: `git clone git@gitserver:/srv/git/project.git`
- `git commit -am`: `git commit -am 'Fix for README file'`
- `which git-shell`: `which git-shell   # make sure git-shell is installed on your system.`
- `-e`: `sudo -e /etc/shells  # and add the path to git-shell from last command`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `fatal: Interactive git shell is not enabled.` | At this point, users are still able to use SSH port forwarding to access any host the git server is able to reach. |

- **Note:** A good deal of what is described here can be automated by using the `ssh-copy-id` command, rather than manually copying and installing public keys.

## Related skills

- `git-getting-git-on-a-server` - Getting Git on a Server
- `git-generating-your-ssh-public-key` - Generating Your SSH Public Key
- `git-the-protocols` - The Protocols
- `git-as-a-client` - Git as a Client

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 119-122, CC BY-NC-SA 3.0._
