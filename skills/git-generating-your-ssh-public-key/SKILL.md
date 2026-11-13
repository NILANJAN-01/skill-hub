---
name: git-generating-your-ssh-public-key
description: "Create an SSH key for GitHub, GitLab or a git server with ssh-keygen. Use when handling Permission denied (publickey)."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Generating Your SSH Public Key"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "118-119"
---

# Generating Your SSH Public Key

The `.pub` file is your public key, and the other file is the corresponding private key.

_Built from "Pro Git" (pages 118-119) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **generating your ssh public key** (git servers authenticate, ssh keys, public keys, user, file).
- The user wants to run or understand `ssh-keygen -o`.
- The user wants to run or understand `cd`.
- The user wants to run or understand `ls`.
- The user wants to run or understand `cat`.

## When NOT to use

- For setting up the server, use the `git-setting-up-the-server` skill instead.
- For getting git on a server, use the `git-getting-git-on-a-server` skill instead.
- For the protocols, use the `git-the-protocols` skill instead.

## Key concepts

- Many Git servers authenticate using SSH public keys.
- In order to provide a public key, each user in your system must generate one if they don’t already have one.
- By default, a user’s SSH keys are stored in that user’s `~/.ssh` directory.
- However, if you do use a password, make sure to add the `-o` option; it saves the private key in a format that is more resistant to brute-force password cracking than is the default format.
- You can also use the `ssh-agent` tool to prevent having to enter the password each time.
- Git server (assuming you’re using an SSH server setup that requires public keys).
- For a more in-depth tutorial on creating an SSH key on multiple operating systems, see the GitHub guide on SSH keys at https://docs.github.com/en/authentication/connecting-to-github-with-ssh/ generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- However, if you do use a password, make sure to add the `-o` option; it saves the private key in a format that is more resistant to brute-force password cracking than is the default format.

## Procedures

### Generating Your SSH Public Key

**Goal:** The `.pub` file is your public key, and the other file is the corresponding private key.

**Steps:**

1. You can easily check to see if you have a key already by going to that directory and listing the contents:
   ```bash
   cd ~/.ssh
   ls
   ```
   Expected output (excerpt):
   ```text
   authorized_keys2  id_dsa       known_hosts
   config            id_dsa.pub
   ```
2. If you don’t have these files (or you don’t even have a `.ssh` directory), you can create them by running a program called `ssh-keygen`, which is provided with the SSH package on Linux/macOS systems and comes with Git for Windows:
   ```bash
   ssh-keygen -o
   ```
   Expected output (excerpt):
   ```text
   Generating public/private rsa key pair.
   Enter file in which to save the key (/home/schacon/.ssh/id_rsa):
   ```
3. Run:
   ```text
   Created directory '/home/schacon/.ssh'.
   Enter passphrase (empty for no passphrase):
   Enter same passphrase again:
   Your identification has been saved in /home/schacon/.ssh/id_rsa.
   Your public key has been saved in /home/schacon/.ssh/id_rsa.pub.
   The key fingerprint is:
   d0:82:24:8e:d7:f1:bb:9b:33:53:96:93:49:da:9b:e3 schacon@mylaptop.local
   ```
4. The public keys look something like this:
   ```bash
   cat ~/.ssh/id_rsa.pub
   ```
   Expected output (excerpt):
   ```text
   ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAklOUpkDHrfHY17SbrmTIpNLTGK9Tjom/BWDSU
   GPl+nafzlHDTYW7hdI4yZ5ew18JH4JW9jbhUFrviQzM7xlELEVf4h9lFX5QVkbPppSwg0cda3
   Pbv7kOdJ/MTyBlWXFCR+HAo3FXRitBqxiX1nKhXpHAZsMciLq8V6RjsNAQwdsdMFvSlVK/7XA
   t3FaoJoAsncM1Q9x5+3V0Ww68/eIFmb1zuUFljQJKprrX88XypNDvjYNby6vw/Pb0rwert/En
   ```

**Verify:** run `cat ~/.ssh/id_rsa.pub` - expect something like:
```text
ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAklOUpkDHrfHY17SbrmTIpNLTGK9Tjom/BWDSU
GPl+nafzlHDTYW7hdI4yZ5ew18JH4JW9jbhUFrviQzM7xlELEVf4h9lFX5QVkbPppSwg0cda3
Pbv7kOdJ/MTyBlWXFCR+HAo3FXRitBqxiX1nKhXpHAZsMciLq8V6RjsNAQwdsdMFvSlVK/7XA
t3FaoJoAsncM1Q9x5+3V0Ww68/eIFmb1zuUFljQJKprrX88XypNDvjYNby6vw/Pb0rwert/En
mZ+AW4OZPnTPI89ZPmVMLuayrD2cE86Z/il8b+gw3r3+1nKatmIkjn2so1d01QraTlMqVSsbx
NrRFi9wrf+M7Q== schacon@mylaptop.local
```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `ssh-keygen -o` | If you don’t have these files (or you don’t even have a `.ssh` directory), you can create them by running a program called `ssh-keygen`, which is provided with the SSH package on Linux/macOS systems and comes with Git for Windows | `ssh-keygen -o` |

## Related skills

- `git-setting-up-the-server` - Setting Up the Server
- `git-getting-git-on-a-server` - Getting Git on a Server
- `git-the-protocols` - The Protocols
- `git-credential-storage` - Credential Storage

## Source

"Pro Git", pages 118-119. Sections: Generating Your SSH Public Key.
