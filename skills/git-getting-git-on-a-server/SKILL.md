---
name: git-getting-git-on-a-server
description: "Getting Git on a Server playbook extracted from \"Pro Git\". However, keep in mind that to collaborate with a couple of people on a private project, all you need is an SSH server and a bare repository. Use when the user asks about getting git on a server, bare repository, git server, ssh server, ssh access, directory, git repository; or mentions git clone --bare, cp -Rf, scp -r, git clone, ssh, cd."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Getting Git on a Server"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "116-118"
---

# Getting Git on a Server

However, keep in mind that to collaborate with a couple of people on a private project, all you need is an SSH server and a bare repository.

_Built from "Pro Git" (pages 116-118) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **getting git on a server** (bare repository, git server, ssh server, ssh access, directory).
- The user wants to run or understand `git clone --bare`.
- The user wants to run or understand `cp -Rf`.
- The user wants to run or understand `scp -r`.
- The user wants to run or understand `git clone`.
- If you want to place your repositories on a server that doesn’t have accounts for everyone on your team for whom you want to grant write access, then you must set up SSH access for them.

## When NOT to use

- For the protocols, use the `git-the-protocols` skill instead.
- For getting a git repository, use the `git-getting-a-git-repository` skill instead.
- For setting up the server, use the `git-setting-up-the-server` skill instead.

## Key concepts

- In order to initially set up any Git server, you have to export an existing repository into a new bare repository — a repository that doesn’t contain a working directory.
- If a user SSHs into a server and has write access to the `/srv/git/my_project.git` directory, they will also automatically have push access.
- You see how easy it is to take a Git repository, create a bare version, and place it on a server to which you and your collaborators have SSH access.
- It’s important to note that this is literally all you need to do to run a useful Git server to which several people have access — just add SSH-able accounts on a server, and stick a bare repository somewhere that all those users have read and write access to.
- One of the most complicated aspects of setting up a Git server is user management.
- If you want to place your repositories on a server that doesn’t have accounts for everyone on your team for whom you want to grant write access, then you must set up SSH access for them.
- Another way to do it is to have your SSH server authenticate from an LDAP server or some other centralized authentication source that you may already have set up.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- Note that by running this command, you will not destroy any commits, refs, etc. in the process.

## Procedures

### Getting Git on a Server

**Goal:** In order to initially set up any Git server, you have to export an existing repository into a new bare repository — a repository that doesn’t contain a working directory.

**Steps:**

1. By convention, bare repository directory names end with the suffix `.git`, like so:
   ```bash
   git clone --bare my_project my_project.git
   ```
   Expected output (excerpt):
   ```text
   Cloning into bare repository 'my_project.git'...
   done.
   ```
2. This is roughly equivalent to something like:
   ```bash
   cp -Rf my_project/.git my_project.git
   ```

### Putting the Bare Repository on a Server

**Goal:** However, keep in mind that to collaborate with a couple of people on a private project, all you need is an SSH server and a bare repository.

**Steps:**

1. Assuming that `/srv/git` exists on that server, you can set up your new repository by copying your bare repository over:
   ```bash
   scp -r my_project.git user@git.example.com:/srv/git
   ```
2. At this point, other users who have SSH-based read access to the `/srv/git` directory on that server can clone your repository by running:
   ```bash
   git clone user@git.example.com:/srv/git/my_project.git
   ```
3. Note that by running this command, you will not destroy any commits, refs, etc. in the process.
   ```bash
   ssh user@git.example.com
   cd /srv/git/my_project.git
   git init --bare --shared
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git clone --bare` | By convention, bare repository directory names end with the suffix `.git`, like so | `git clone --bare my_project my_project.git` |
| `scp -r` | Assuming that `/srv/git` exists on that server, you can set up your new repository by copying your bare repository over | `scp -r my_project.git user@git.example.com:/srv/git` |
| `git clone` | At this point, other users who have SSH-based read access to the `/srv/git` directory on that server can clone your repository by running | `git clone user@git.example.com:/srv/git/my_project.git` |
| `ssh` | However, keep in mind that to collaborate with a couple of people on a private project, all you need is an SSH server and a bare repository. | `ssh user@git.example.com` |
| `git init --bare --shared` | Note that by running this command, you will not destroy any commits, refs, etc. in the process. | `git init --bare --shared` |

## Troubleshooting

- **Note:** Here we’ll be demonstrating the commands and steps needed to do basic, simplified installations on a Linux-based server, though it’s also possible to run these services on macOS or Windows servers. Actually setting up a production server within your infrastructure will certainly entail differences in security measures or operating system tools, but hopefully this will give you the general idea of what’s involved.

## Related skills

- `git-the-protocols` - The Protocols
- `git-getting-a-git-repository` - Getting a Git Repository
- `git-setting-up-the-server` - Setting Up the Server
- `git-daemon` - Git Daemon

## Source

"Pro Git", pages 116-118. Sections: Getting Git on a Server; Getting Git on a Server > Putting the Bare Repository on a Server; Getting Git on a Server > Small Setups.
