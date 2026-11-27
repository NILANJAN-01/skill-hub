---
name: git-distributed-git-contributing-to-a-project
description: "Contribute with plain git: commit guidelines, team workflows, patches by email. Use when you need to prepare commits or patches for upstream."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Contributing to a Project"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "135-156"
---

# Contributing to a Project

Because Git is very flexible, people can and do work together in many ways, and it’s problematic to describe how you should contribute — every project is a bit different.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git rebase origin/master`
  - `git push -f myfork featureA`
- **Note (from source):** You may want to use `rebase -i` to squash your work down to a single commit, or rearrange the work in the commits to make the patch easier for the maintainer to review — see Rewriting History for more information about interactive rebasing.
- Rewriting History describes a number of useful Git tricks for rewriting history and interactively staging files — use these tools to help craft a clean and understandable history before sending the work to someone else.
- On a project for which you’re not the maintainer, it’s generally easier to have a branch like `master` always track `origin/master` and to do your work in topic branches that you can easily discard if they’re rejected.

## Commands

- `git push`
- `git commit -am`: `git commit -am 'Add ls-files'`
- `git fetch`: `git fetch origin`
- `git checkout -b`: `git checkout -b topicA`
- `git commit`
- `git merge`: `git merge issue54`
- `git clone`: `git clone <url>`
- `git checkout`: `git checkout master`
- `git push -u`: `git push -u origin featureA`
- `git request-pull`: `git request-pull origin/master myfork`
- `git log --no-merges`: `git log --no-merges issue54..origin/master`
- `git log`: `git log featureA..origin/featureA`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `! [rejected]        master -> master (non-fast forward)` | In this case, John’s push fails because of Jessica’s earlier push of her changes. |

- **Note:** Do as we say, not as we do. For the sake of brevity, many of the examples in this book don’t have nicely-formatted commit messages like this; instead, we simply use the `-m` option to `gitcommit`.
- **Tip:** For help on configuring your system and email, more tips and tricks, and a sandbox to send a trial patch via email, go to git-send-email.io.

## Related skills

- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-github-contributing-to-a-project` - Contributing to a Project
- `git-as-a-client` - Git as a Client
- `git-rebasing` - Rebasing

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 135-156, CC BY-NC-SA 3.0._
