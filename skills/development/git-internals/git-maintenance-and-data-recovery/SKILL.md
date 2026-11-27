---
name: git-maintenance-and-data-recovery
description: "Recover lost commits (reflog, fsck) and shrink a repository (gc, large files). Use when you are after reset --hard or for a huge .git."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Maintenance and Data Recovery"
  category: git-internals
  source: "Pro Git, 2nd edition"
  pages: "446-453"
---

# Maintenance and Data Recovery

Because the reflog data is kept in the `.git/logs/` directory, you effectively have no reflog.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git reset --hard 1a410efbd13591db07496601ebc7a059dd55cfe9`
  - `git branch -D recover-branch`
  - `git filter-branch --index-filter \`
  - `git prune --expire now`
- Occasionally, you may have to do some cleanup – make a repository more compact, clean up an imported repository, or recover lost work.
- At some point in your Git journey, you may accidentally lose a commit.
- Generally, this happens because you force-delete a branch that had work on it, and it turns out you wanted the branch after all; or you hard-reset a branch, thus abandoning commits that you wanted something from.

## Commands

- `git log --pretty`: `git log --pretty=oneline`
- `git count-objects -v`
- `git commit -m`: `git commit -m 'Add git tarball'`
- `git gc`
- `git gc --auto`
- `git reset --hard`: `git reset --hard 1a410efbd13591db07496601ebc7a059dd55cfe9`
- `git reflog`
- `git log -g`
- `git branch`: `git branch recover-branch ab1afef`
- `git branch -D`: `git branch -D recover-branch`
- `git fsck --full`
- `curl -L`: `curl -L https://www.kernel.org/pub/software/scm/git/git-2.1.0.tar.gz > git.tgz`

## Related skills

- `git-references` - Git References
- `git-packfiles` - Packfiles
- `git-migrating-to-git` - Migrating to Git
- `git-objects` - Git Objects

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 446-453, CC BY-NC-SA 3.0._
