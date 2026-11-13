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

_Built from "Pro Git" (pages 111-116) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **the protocols** (git repository, git http smart, ssh protocol, access, http protocol).
- The user wants to run or understand `git clone`.
- The user wants to run or understand `cd`.
- The user wants to run or understand `git remote`.
- The user wants to run or understand `git clone --bare`.
- Smart HTTP operates very similarly to the SSH or Git protocols but runs over standard HTTPS ports and can use various HTTP authentication mechanisms, meaning it’s often easier on the user than something like SSH, since you can use things like username/password authentication rather than having to set up SSH keys.

## When NOT to use

- For transfer protocols, use the `git-transfer-protocols` skill instead.
- For getting git on a server, use the `git-getting-git-on-a-server` skill instead.
- For git daemon, use the `git-daemon` skill instead.

## Key concepts

- Git can use four distinct protocols to transfer data: Local, HTTP, Secure Shell (SSH) and Git.
- Smart HTTP operates very similarly to the SSH or Git protocols but runs over standard HTTPS ports and can use various HTTP authentication mechanisms, meaning it’s often easier on the user than something like SSH, since you can use things like username/password authentication rather than having to set up SSH keys.
- It has probably become the most popular way to use Git now, since it can be set up to both serve anonymously like the `git://` protocol, and can also be pushed over with authentication and encryption like the SSH protocol.
- If the server does not respond with a Git HTTP smart service, the Git client will try to fall back to the simpler Dumb HTTP protocol.
- The Dumb protocol expects the bare Git repository to be served like normal files from the web server.
- Other than that, there is very little advantage that other protocols have over Smart HTTP for serving Git content.
- This is a special daemon that comes packaged with Git; it listens on a dedicated port (9418) that provides a service similar to the SSH protocol, but with absolutely no authentication or cryptography.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Local Protocol

**Goal:** The most basic is the Local protocol, in which the remote repository is in another directory on the same host.

**Steps:**

1. For example, to clone a local repository, you can run something like this:
   ```bash
   git clone /srv/git/project.git
   ```
2. Or you can do this:
   ```bash
   git clone file:///srv/git/project.git
   ```
3. To add a local repository to an existing Git project, you can run something like this:
   ```bash
   git remote add local_proj /srv/git/project.git
   ```

### The HTTP Protocols

**Goal:** Smart HTTP operates very similarly to the SSH or Git protocols but runs over standard HTTPS ports and can use various HTTP authentication mechanisms, meaning it’s often easier on the user than something like SSH, since you can use things like username/password authentication rather than having to set up SSH keys.

**Steps:**

1. To allow read access to your repository over HTTP, do something like this:
   ```bash
   cd /var/www/htdocs/
   git clone --bare /path/to/git_project gitproject.git
   cd gitproject.git
   mv hooks/post-update.sample hooks/post-update
   chmod a+x hooks/post-update
   ```
2. This command is run when you push to this repository (over SSH perhaps); then, other people can clone via something like:
   ```bash
   git clone https://example.com/gitproject.git
   ```

### The SSH Protocol

**Goal:** A common transport protocol for Git when self-hosting is over SSH.

**Steps:**

1. To clone a Git repository over SSH, you can specify an `ssh://` URL like this:
   ```bash
   git clone ssh://[user@]server/project.git
   ```
2. Or you can use the shorter scp-like syntax for the SSH protocol:
   ```bash
   git clone [user@]server:project.git
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git clone` | Running `git clonehttp://example.com/project.git` should be avoided for the same reason. | `git clone /srv/git/project.git` |
| `git remote` | To add a local repository to an existing Git project, you can run something like this | `git remote add local_proj /srv/git/project.git` |
| `git clone --bare` | To allow read access to your repository over HTTP, do something like this | `git clone --bare /path/to/git_project gitproject.git` |
| `chmod` | To allow read access to your repository over HTTP, do something like this | `chmod a+x hooks/post-update` |

## Decision guide

- Instead of having to set up different URLs for these things, you can now use a single URL for both.
- If you try to push and the repository requires authentication (which it normally should), the server can prompt for a username and password.

## Related skills

- `git-transfer-protocols` - Transfer Protocols
- `git-getting-git-on-a-server` - Getting Git on a Server
- `git-daemon` - Git Daemon
- `git-getting-a-git-repository` - Getting a Git Repository

## Source

"Pro Git", pages 111-116. Sections: The Protocols; The Protocols > Local Protocol; The Protocols > The HTTP Protocols; The Protocols > The SSH Protocol; The Protocols > The Git Protocol.
