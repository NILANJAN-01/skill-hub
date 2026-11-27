---
name: git-rewriting-history
description: "Amend, squash, reorder or drop commits; remove a file or secret from all history. Use when you need to edit past commits."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Rewriting History"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "249-257"
---

# Rewriting History

`filter-branch` is the tool you probably want to use to scrub your entire history.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git commit --amend`
  - `git commit --amend --no-edit`
  - `git rebase -i HEAD~3`
  - `git rebase --continue`
  - `git filter-branch --tree-filter 'rm -f passwords.txt' HEAD`
  - `git filter-branch --subdirectory-filter trunk HEAD`
  - `git filter-branch --commit-filter '`
- **Note (from source):** Don’t push your work until you’re happy with it One of the cardinal rules of Git is that, since so much work is local within your clone, you have a great deal of freedom to rewrite your history locally. However, once you push your work, it is a different story entirely, and you should consider pushed work as final unless you have good reason to change it. In short, you should avoid pushing your work until you’re happy with it and ready to share it with the rest of the world.
- **Caution (from source):** `git filter-branch` has many pitfalls, and is no longer the recommended way to rewrite history. Instead, consider using `git-filter-repo`, which is a Python script that does a better job for most applications where you would normally turn to `filter-branch`.
- **Caution (from source):** https://github.com/newren/git-filter-repo.

## Commands

- `git commit --amend`
- `git rebase -i`: `git rebase -i HEAD~3`
- `git log --pretty`: `git log -4 --pretty=format:"%h %s"`
- `git rebase --continue`
- `git add`: `git add README`
- `git commit -m`: `git commit -m 'Add blame'`
- `git commit --amend --no-edit`
- `git reset`: `git reset HEAD^`
- `git filter-branch --tree-filter -f`: `git filter-branch --tree-filter 'rm -f passwords.txt' HEAD`
- `git filter-branch --subdirectory-filter`: `git filter-branch --subdirectory-filter trunk HEAD`
- `git filter-branch --commit-filter`: `git filter-branch --commit-filter '`

## Troubleshooting

- **Tip:** An amended commit may (or may not) need an amended commit message When you amend a commit, you have the opportunity to change both the commit message and the content of the commit. If you amend the content of the commit substantially, you should almost certainly update the commit message to reflect that amended content.
- **Note:** Drew DeVault made a practical hands-on guide with exercises to learn how to use `git rebase`. You can find it at: https://git-rebase.io/

## Related skills

- `git-rebasing` - Rebasing
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-as-a-client` - Git as a Client

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 249-257, CC BY-NC-SA 3.0._
