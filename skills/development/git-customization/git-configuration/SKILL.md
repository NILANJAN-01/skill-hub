---
name: git-configuration
description: "Change git settings: editor, pager, colours, diff/merge tools, autocrlf, whitespace. Use when handling git config or CRLF problems."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git Configuration"
  category: git-customization
  source: "Pro Git, 2nd edition"
  pages: "342-352"
---

# Git Configuration

As you read briefly in Getting Started, you can specify Git configuration settings with the `git config` command.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- …and you run `git config --global core.excludesfile ~/.gitignore_global`, Git will never again bother you about those files.
- You’ll rarely want this; in most scenarios, if you want color codes in your redirected output, you can instead pass a `--color` flag to the Git command to force it to use color codes.
- This is generally good policy; but in the case of the rebase, you may determine that you know what you’re doing and can force-update the remote branch with a `-f` flag to your push command.

## Commands

- `git config --global`: `git config --global core.pager ''`
- `git config --system`: `git config --system receive.fsckObjects true`
- `git chekcout`: `git chekcout master`
- `chmod`: `sudo chmod +x /usr/local/bin/extDiff`
- `git apply --whitespace`: `git apply --whitespace=fix <patch>`
- `man git-config`
- `git commit`
- `git tag -s`: `git tag -s <tag-name>`
- `git diff`: `git diff 32d1776b1^ 32d1776b1`
- `git mergetool --tool-help`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `WARNING: You called a Git command named 'chekcout', which does not exist.` | Note that “0.1 seconds” business. |

- **Note:** Git’s configuration files are plain-text, so you can also set these values by manually editing the file and inserting the correct syntax. It’s generally easier to run the `gitconfig` command, though.
- **Note:** For advanced use cases you may want to look up "Conditional includes" in the documentation mentioned above.

## Related skills

- `git-first-time-git-setup` - First-Time Git Setup
- `git-setup-and-config` - Setup and Config
- `git-an-example-git-enforced-policy` - An Example Git-Enforced Policy
- `git-environment-variables` - Environment Variables

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 342-352, CC BY-NC-SA 3.0._
