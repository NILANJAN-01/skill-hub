---
name: git-hooks
description: "Write git hooks (pre-commit, commit-msg, pre-push, pre-receive). Use when you need to run a script automatically on commit, push or merge."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git Hooks"
  category: git-customization
  source: "Pro Git, 2nd edition"
  pages: "360-363"
---

# Git Hooks

This hook takes a few parameters: the path to the file that holds the commit message so far, the type of commit, and the commit SHA-1 if this is an amended commit.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- This script can’t stop the push process, but the client doesn’t disconnect until it has completed, so be careful if you try to do anything that may take a long time.

## Troubleshooting

- **Note:** It’s important to note that client-side hooks are not copied when you clone a repository. If your intent with these scripts is to enforce a policy, you’ll probably want to do that on the server side; see the example in An Example Git-Enforced Policy.
- **Tip:** If you’re writing a script/hook that others will need to read, prefer the long versions of command-line flags; six months from now you’ll thank us.

## Related skills

- `git-an-example-git-enforced-policy` - An Example Git-Enforced Policy
- `git-scripting-github` - Scripting GitHub
- `git-as-a-client` - Git as a Client
- `git-configuration` - Git Configuration

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 360-363, CC BY-NC-SA 3.0._
