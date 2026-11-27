---
name: git-in-powershell
description: "Set up git in PowerShell with posh-git: prompt status and tab completion. Use when handling a git prompt on Windows PowerShell."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git in PowerShell"
  category: git-integrations
  source: "Pro Git, 2nd edition"
  pages: "469-471"
---

# Git in PowerShell

Before you’re able to run PowerShell scripts on your machine, you need to set your local `ExecutionPolicy` to `RemoteSigned` (basically, anything except `Undefined` and `Restricted`).

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Related skills

- `git-installing-git` - Installing Git
- `git-scripting-github` - Scripting GitHub
- `git-configuration` - Git Configuration

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 469-471, CC BY-NC-SA 3.0._
