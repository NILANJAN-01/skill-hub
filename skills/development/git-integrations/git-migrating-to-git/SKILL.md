---
name: git-migrating-to-git
description: "Convert a Subversion, Mercurial or Perforce repository to git. Use when you need to import another VCS history."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Migrating to Git"
  category: git-integrations
  source: "Pro Git, 2nd edition"
  pages: "405-419"
---

# Migrating to Git

If you want to map this to better Git author data, you need a mapping from the Subversion users to the Git authors.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `for p in $(git for-each-ref --format='%(refname:short)' | grep @); do git branch -D`
  - `git filter-branch --msg-filter 'sed -e "/^\[git-p4:/d"'`
  - `git reset --hard master`
- That generates the log output in XML format, then keeps only the lines with author information, discards duplicates, strips out the XML tags.

## Commands

- `git log`: `git log -2`
- `for --format`: `for t in $(git for-each-ref --format='%(refname:short)' refs/remotes/tags); do git`
- `git remote`: `git remote add origin git@my-git-server:myrepository.git`
- `git push --all`: `git push origin --all`
- `git init`
- `/tmp/fast-export/hg-fast-export.sh -r -A`: `/tmp/fast-export/hg-fast-export.sh -r /tmp/hg-repo -A /tmp/authors`
- `ruby`: `ruby import.rb /opt/import_from`
- `svn log --xml --quiet`: \`
- `git svn --authors-file --no-metadata`: `git svn clone http://my-project.googlecode.com/svn/ \`
- `for --format -D`: grep @); do git branch -D`
- `git branch -d`: `git branch -d trunk`
- `git push --tags`: `git push origin --tags`

## Troubleshooting

- **Note:** If you’re trying this on a Windows machine, this is the point where you’ll run into trouble.
- **Note:** https://learn.microsoft.com/en-us/azure/devops/repos/git/perform-migration-from-svn-to-git.

## Related skills

- `git-as-a-client` - Git as a Client
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-configuration` - Git Configuration

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 405-419, CC BY-NC-SA 3.0._
