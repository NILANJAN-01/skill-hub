---
name: git-setting-up-the-server
description: "Set up an SSH git server: a git user, authorized_keys, a bare repository, and restricting the account with git-shell. Use when the user wants several developers to push to a self-hosted repository over SSH."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Setting Up the Server"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "119-122"
---

# Setting Up the Server

With this method, you can quickly get a read/write Git server up and running for a handful of developers.

_Built from "Pro Git" (pages 119-122) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **setting up the server** (ssh public keys, git server, user account, walk through setting, authorized).
- The user wants to run or understand `cat`.
- The user wants to run or understand `cd`.
- The user wants to run or understand `mkdir`.
- The user wants to run or understand `git push`.
- The user sees an error like `fatal: Interactive git shell is not enabled.`.

## When NOT to use

- For getting git on a server, use the `git-getting-git-on-a-server` skill instead.
- For generating your ssh public key, use the `git-generating-your-ssh-public-key` skill instead.
- For the protocols, use the `git-the-protocols` skill instead.

## Key concepts

- In this example, you’ll use the `authorized_keys` method for authenticating your users.
- You should note that currently all these users can also log into the server and get a shell as the `git` user.
- You can easily restrict the `git` user account to only Git-related activities with a limited shell tool called `git-shell` that comes with Git.
- If you set this as the `git` user account’s login shell, then that account can’t have normal shell access to your server.
- To use this, specify `git-shell` instead of `bash` or `csh` for that account’s login shell.
- As the output states, you can also set up a directory in the `git` user’s home directory that customizes the `git-shell` command a bit.
- Run `git helpshell` for more information on customizing the shell.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Setting Up the Server

**Goal:** With this method, you can quickly get a read/write Git server up and running for a handful of developers.

**Steps:**

1. First, you create a `git` user account and a `.ssh` directory for that user.
   ```bash
   sudo adduser git
   su git
   cd
   mkdir .ssh && chmod 700 .ssh
   touch .ssh/authorized_keys && chmod 600 .ssh/authorized_keys
   ```
2. Again, the public keys look something like this:
   ```bash
   cat /tmp/id_rsa.john.pub
   ```
   Expected output (excerpt):
   ```text
   ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCB007n/ww+ouN4gSLKssMxXnBOvf9LGt4L
   ojG6rs6hPB09j9R/T17/x4lhJA0F3FR1rP6kYBRsWj2aThGw6HXLm9/5zytK6Ztg3RPKK+4k
   Yjh6541NYsnEAZuXz0jTTyAUfrtU3Z5E003C4oxOj6H0rfIF1kKI9MAQLMdpGW1GYEIgS9Ez
   Sdfd8AcCIicTDWbqLAcU4UpkaX8KyGlLwsNuuGztobF8m72ALC/nLF6JLtPofwFBlgc+myiv
   ```
3. You just append them to the `git` user’s `authorized_keys` file in its `.ssh` directory:
   ```bash
   cat /tmp/id_rsa.john.pub >> ~/.ssh/authorized_keys
   cat /tmp/id_rsa.josie.pub >> ~/.ssh/authorized_keys
   cat /tmp/id_rsa.jessica.pub >> ~/.ssh/authorized_keys
   ```
4. Now, you can set up an empty repository for them by running `git init` with the `--bare` option, which initializes the repository without a working directory:
   ```bash
   cd /srv/git
   mkdir project.git
   cd project.git
   git init --bare
   ```
   Expected output (excerpt):
   ```text
   Initialized empty Git repository in /srv/git/project.git/
   ```
5. If you’re running it internally, and you set up DNS for `gitserver` to point to that server, then you can use the commands pretty much as is (assuming that `myproject` is an existing project with files in it):
   ```bash
   cd myproject
   git init
   git add .
   git commit -m 'Initial commit'
   git remote add origin git@gitserver:/srv/git/project.git
   git push origin master
   ```
6. At this point, the others can clone it down and push changes back up just as easily:
   ```bash
   git clone git@gitserver:/srv/git/project.git
   ```

_7 more step(s) in references/procedures.md._

**Verify:** run `cat ~/.ssh/authorized_keys` - expect something like:
```text
no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-rsa
AAAAB3NzaC1yc2EAAAADAQABAAABAQCB007n/ww+ouN4gSLKssMxXnBOvf9LGt4LojG6rs6h
```

More procedures in [references/procedures.md](references/procedures.md):

- Setting Up the Server

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git push` | If you’re running it internally, and you set up DNS for `gitserver` to point to that server, then you can use the commands pretty much as is (assuming that `myproject` is an existing project with files in it) | `git push origin master` |
| `adduser git` | First, you create a `git` user account and a `.ssh` directory for that user. | `sudo adduser git` |
| `su git` | First, you create a `git` user account and a `.ssh` directory for that user. | `su git` |
| `git init --bare` | Now, you can set up an empty repository for them by running `git init` with the `--bare` option, which initializes the repository without a working directory | `git init --bare` |
| `git init` | Now, you can set up an empty repository for them by running `git init` with the `--bare` option, which initializes the repository without a working directory | `git init` |
| `git add` | If you’re running it internally, and you set up DNS for `gitserver` to point to that server, then you can use the commands pretty much as is (assuming that `myproject` is an existing project with files in it) | `git add .` |
| `git commit -m` | If you’re running it internally, and you set up DNS for `gitserver` to point to that server, then you can use the commands pretty much as is (assuming that `myproject` is an existing project with files in it) | `git commit -m 'Initial commit'` |
| `git remote` | If you’re running it internally, and you set up DNS for `gitserver` to point to that server, then you can use the commands pretty much as is (assuming that `myproject` is an existing project with files in it) | `git remote add origin git@gitserver:/srv/git/project.git` |
| `git clone` | At this point, the others can clone it down and push changes back up just as easily | `git clone git@gitserver:/srv/git/project.git` |
| `git commit -am` | At this point, the others can clone it down and push changes back up just as easily | `git commit -am 'Fix for README file'` |
| `which git-shell` | To do so, you must first add the full pathname of the `git-shell` command to `/etc/shells` if it’s not already there | `which git-shell   # make sure git-shell is installed on your system.` |
| `-e` | To do so, you must first add the full pathname of the `git-shell` command to `/etc/shells` if it’s not already there | `sudo -e /etc/shells  # and add the path to git-shell from last command` |
| `chsh git -s` | Now you can edit the shell for a user using `chsh <username> -s <shell>` | `sudo chsh git -s $(which git-shell)` |
| `ssh` | Let’s walk through setting up SSH access on the server side. | `ssh git@gitserver` |

## Decision guide

- To use this, specify `git-shell` instead of `bash` or `csh` for that account’s login shell.

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

## Source

"Pro Git", pages 119-122. Sections: Setting Up the Server.
