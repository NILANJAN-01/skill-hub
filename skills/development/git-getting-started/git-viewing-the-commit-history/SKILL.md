---
name: git-viewing-the-commit-history
description: "View and filter history with git log (--oneline, --graph, --stat, by author or date). Use when you need to see or format the commit log."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Viewing the Commit History"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "46-52"
---

# Viewing the Commit History

Another really helpful filter is the `-S` option (colloquially referred to as Git’s “pickaxe” option), which takes a string and shows only those commits that changed the number of occurrences of that string.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `git log`
- `git log --pretty`: `git log --pretty=oneline`
- `git clone`: `git clone https://github.com/schacon/simplegit-progit`
- `git log -p`: `git log -p -2`
- `git log --stat`
- `git log --pretty --graph`: `git log --pretty=format:"%h %s" --graph`
- `git log --since`: `git log --since=2.weeks`
- `git log -S`: `git log -S function_name`
- `git log --pretty --author`: `git log --pretty="%h - %s" --author='Junio C Hamano' --since="2008-10-01" \`

## Troubleshooting

- **Note:** You can specify more than one instance of both the `--author` and `--grep` search criteria, which will limit the commit output to commits that match any of the `--author` patterns and any of the `--grep` patterns; however, adding the `--all-match` option further limits the output to just those commits that match all`--grep` patterns.
- **Tip:** Preventing the display of merge commits Depending on the workflow used in your repository, it’s possible that a sizable percentage of the commits in your log history are just merge commits, which typically aren’t very informative. To prevent the display of merge commits cluttering up your log history, simply add the `log` option `--no-merges`.

## Related skills

- `git-searching` - Searching
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-rewriting-history` - Rewriting History

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 46-52, CC BY-NC-SA 3.0._
