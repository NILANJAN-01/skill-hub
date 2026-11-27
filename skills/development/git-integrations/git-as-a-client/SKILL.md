---
name: git-as-a-client
description: "Use git against a Subversion, Mercurial or Perforce server (git svn, git p4). Use when the team repo is not git."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git as a Client"
  category: git-integrations
  source: "Pro Git, 2nd edition"
  pages: "373-405"
---

# Git as a Client

This tool allows you to use Git as a valid client to a Subversion server, so you can use all the local features of Git and then push to a Subversion server as if you were using Subversion locally.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git svn rebase`
  - `git p4 rebase`
- Don’t rewrite your history and try to push again, and don’t push to a parallel Git repository to collaborate with fellow Git developers at the same time.
- The branch name “permanent” was recorded with the changeset marked 7.
- One thing you should know is that Mercurial doesn’t support rewriting history, only adding to it.

## Commands

- `git svn`: `git svn log`
- `git log --oneline --all`: `git log --oneline --all --graph --decorate`
- `git p4`: `git p4 sync`
- `git log --oneline --graph`: `git log --oneline --graph --decorate`
- `git push`
- `git clone`: `git clone https://10.0.1.254/Jam`
- `export`: `export P4USER=john`
- `git log --oneline --decorate`: `git log --oneline --decorate --graph --all`
- `chmod`: `chmod +x ~/bin/git-remote-hg`
- `git branch -a`
- `git show-ref`
- `git commit -am`: `git commit -am 'A permanent change'`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `ERROR from SVN:` | To resolve this situation, you can run `git svn rebase`, which pulls down any changes on the server that you don’t have yet and rebases any work you have on top of what is on the server: |

- **Note:** You’ll need the `p4` tool somewhere in your `PATH` to work with git-p4. As of this writing, it is freely available at https://www.perforce.com/downloads/helix-command-line-client-p4.

## Related skills

- `git-migrating-to-git` - Migrating to Git
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-advanced-merging` - Advanced Merging
- `git-branches-in-a-nutshell` - Branches in a Nutshell

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 373-405, CC BY-NC-SA 3.0._
