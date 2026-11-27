---
name: git-distributed-git-maintaining-a-project
description: "Maintain a project with plain git: apply patches, review branches, cut releases. Use when integrating other people's work."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Maintaining a Project"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "156-171"
---

# Maintaining a Project

This can consist of accepting and applying patches generated via `format-patch` and emailed to you, or integrating changes in remote branches for repositories you’ve added as remotes to your project.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- That is probably the simplest workflow, but it can possibly be problematic if you’re dealing with larger or more stable projects where you want to be really careful about what you introduce.

## Commands

- `git diff`: `git diff master`
- `git am`: `git am 0001-limit-log-function.patch`
- `git checkout -b`: `git checkout -b sc/ruby_client master`
- `git branch`: `git branch sc/ruby_client master`
- `git apply`: `git apply /tmp/patch-ruby-client.patch`
- `git apply --check`: `git apply --check 0001-see-if-this-helps-the-gem.patch`
- `git log --pretty`: `git log --pretty=fuller -1`
- `(fix the`: `(fix the file)`
- `git add`: `git add ticgit.gemspec`
- `git am --resolved`
- `git am -i`: `git am -3 -i mbox`
- `git remote`: `git remote add jessica https://github.com/jessica/myproject.git`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error: patch failed: ticgit.gemspec:1` | If there is no output, then the patch should apply cleanly. |
| `error: ticgit.gemspec: patch does not apply` | In this case, without the `-3` option the patch would have been considered as a conflict. |

## Related skills

- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-github-maintaining-a-project` - Maintaining a Project
- `git-github-contributing-to-a-project` - Contributing to a Project
- `git-rebasing` - Rebasing

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 156-171, CC BY-NC-SA 3.0._
