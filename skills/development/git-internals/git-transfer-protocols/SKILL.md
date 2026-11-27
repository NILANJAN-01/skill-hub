---
name: git-transfer-protocols
description: "How git fetch and push work on the wire: dumb and smart HTTP, send-pack, upload-pack. Use when you need to debug protocol-level problems."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Transfer Protocols"
  category: git-internals
  source: "Pro Git, 2nd edition"
  pages: "441-446"
---

# Transfer Protocols

If you’re setting up a repository to be served read-only over HTTP, the dumb protocol is likely what will be used.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `ssh -x`: `ssh -x git@server "git-upload-pack 'simplegit-progit.git'"`
- `git clone`: `git clone http://server/simplegit-progit.git`
- `git cat-file -p`: `git cat-file -p ca82a6dff817ec66f44342007202690a93763949`

## Troubleshooting

- **Note:** The dumb protocol is fairly rarely used these days. It’s difficult to secure or make private, so most Git hosts (both cloud-based and on-premises) will refuse to use it. It’s generally advised to use the smart protocol, which we describe a bit further on.

## Related skills

- `git-the-protocols` - The Protocols
- `git-bundling` - Bundling
- `git-references` - Git References
- `git-as-a-client` - Git as a Client

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 441-446, CC BY-NC-SA 3.0._
