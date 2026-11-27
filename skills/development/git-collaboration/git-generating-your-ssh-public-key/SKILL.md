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

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- However, if you do use a password, make sure to add the `-o` option; it saves the private key in a format that is more resistant to brute-force password cracking than is the default format.

## Commands

- `ssh-keygen -o`

## Related skills

- `git-setting-up-the-server` - Setting Up the Server
- `git-getting-git-on-a-server` - Getting Git on a Server
- `git-the-protocols` - The Protocols
- `git-credential-storage` - Credential Storage

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 118-119, CC BY-NC-SA 3.0._
