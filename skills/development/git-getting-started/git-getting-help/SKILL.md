---
name: git-getting-help
description: "Look up git docs with git help, --help and man. Use when asked how to find a git command's options."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Getting Help"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "30-31"
---

# Getting Help

These channels are regularly filled with hundreds of people who are all very knowledgeable about Git and are often willing to help.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git help`: `git help <verb>`
- `git --help`: `git <verb> --help`
- `man`: `man git-<verb>`
- `git add -h`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `errors` | See references/source-text.md for this section. |

## Related skills

- `git-setup-and-config` - Setup and Config
- `git-configuration` - Git Configuration

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 30-31, CC BY-NC-SA 3.0._
