---
name: git-daemon
description: "Git Daemon playbook extracted from \"Pro Git\". The --reuseaddr option allows the server to restart without waiting for old connections to time out, while the --base-path option allows people to clone projects without specifying the entire path, and the path at the end tells the Git daemon where to... Use when the user asks about git daemon, ’re running, git daemon, daemon serving repositories, git protocol, system, git data; or mentions git daemon --reuseaddr --base-path, touch git-daemon-export-ok, cd."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git Daemon"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "122-123"
---

# Git Daemon

The `--reuseaddr` option allows the server to restart without waiting for old connections to time out, while the `--base-path` option allows people to clone projects without specifying the entire path, and the path at the end tells the Git daemon where to look for repositories to export.

_Built from "Pro Git" (pages 122-123) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **git daemon** (’re running, git daemon, daemon serving repositories, git protocol, system).
- The user wants to run or understand `git daemon --reuseaddr --base-path`.
- The user wants to run or understand `touch git-daemon-export-ok`.
- The user wants to run or understand `cd`.

## When NOT to use

- For the protocols, use the `git-the-protocols` skill instead.
- For getting git on a server, use the `git-getting-git-on-a-server` skill instead.
- For smart http, use the `git-smart-http` skill instead.

## Key concepts

- This is a common choice for fast, unauthenticated access to your Git data.
- If you’re running this on a server outside your firewall, it should be used only for projects that are publicly visible to the world.
- If the server you’re running it on is inside your firewall, you might use it for projects that a large number of people or computers (continuous integration or build servers) have read-only access to, when you don’t want to have to add an SSH key for each.
- You can daemonize this process a number of ways, depending on the operating system you’re running.
- You might have noticed that Git daemon is started here with `git` as both group and user.
- You can do this in each repository by creating a file named `git-daemon-export-ok`.
- The presence of that file tells Git that it’s OK to serve this project without authentication.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Git Daemon

**Goal:** The `--reuseaddr` option allows the server to restart without waiting for old connections to time out, while the `--base-path` option allows people to clone projects without specifying the entire path, and the path at the end tells the Git daemon where to look for repositories to export.

**Steps:**

1. Basically, you need to run this command in a daemonized manner:
   ```bash
   git daemon --reuseaddr --base-path=/srv/git/ /srv/git/
   ```
2. Simply place a file in `/etc/systemd/system/git-daemon.service` with these contents:
   ```ini
   [Unit]
   Description=Start Git Daemon
   [Service]
   ExecStart=/usr/bin/git daemon --reuseaddr --base-path=/srv/git/ /srv/git/
   ```
3. Run:
   ```ini
   Restart=always
   RestartSec=500ms
   StandardOutput=syslog
   StandardError=syslog
   SyslogIdentifier=git-daemon
   User=git
   Group=git
   [Install]
   WantedBy=multi-user.target
   ```
4. You can do this in each repository by creating a file named `git-daemon-export-ok`.
   ```bash
   cd /path/to/project.git
   touch git-daemon-export-ok
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git daemon --reuseaddr --base-path` | Basically, you need to run this command in a daemonized manner | `git daemon --reuseaddr --base-path=/srv/git/ /srv/git/` |

## Decision guide

- If you’re running this on a server outside your firewall, it should be used only for projects that are publicly visible to the world.

## Related skills

- `git-the-protocols` - The Protocols
- `git-getting-git-on-a-server` - Getting Git on a Server
- `git-smart-http` - Smart HTTP
- `git-setting-up-the-server` - Setting Up the Server

## Source

"Pro Git", pages 122-123. Sections: Git Daemon.
