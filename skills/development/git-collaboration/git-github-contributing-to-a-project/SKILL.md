---
name: git-github-contributing-to-a-project
description: "Contribute on GitHub: fork, branch, pull request, sync with upstream. Use when you need to open or update a pull request or sync a fork."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Contributing to a Project"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "177-197"
---

# Contributing to a Project

This is the basic workflow that most GitHub projects use.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- If you absolutely wish to rebase the branch to clean it up, you can certainly do so, but it is highly encouraged to not force push over the branch that the Pull Request is already opened on.
- But your GitHub repository will never be automatically updated by GitHub; this is something that you must do yourself.

## Commands

- `git push`: `git push ③`
- `git remote`: `git remote add upstream https://github.com/schacon/blink ①`
- `git fetch`: `git fetch progit ②`
- `git checkout`: `git checkout master ①`
- `git pull`: `git pull ②`
- `git clone`: `git clone https://github.com/tonychacon/blink ①`
- `git checkout -b`: `git checkout -b slow-blink ②`
- `sed -i`: `sed -i '' 's/1000/3000/' blink.ino (macOS) ③`
- `git diff --word-diff`: `git diff --word-diff ④`
- `git commit -a -m`: `git commit -a -m 'Change delay to 3 seconds' ⑤`
- `git merge`: `git merge upstream/master ③`
- `git add`: `git add blink.ino`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `CONFLICT (content): Merge conflict in blink.ino` | `①`Add the original repository as a remote named `upstream`. |

- **Note:** Historically, the term “fork” has been somewhat negative in context, meaning that someone took an open source project in a different direction, sometimes creating a competing project and splitting the contributors. In GitHub, a “fork” is simply the same project in your own namespace, allowing you to make changes to a project publicly as a way to contribute in a more open manner.
- **Tip:** You can use the official GitHub CLI tool instead of the GitHub web interface for most things. The tool can be used on Windows, macOS, and Linux systems. Go to the GitHub CLI homepage for installation instructions and the manual.

## Related skills

- `git-github-maintaining-a-project` - Maintaining a Project
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-scripting-github` - Scripting GitHub

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 177-197, CC BY-NC-SA 3.0._
