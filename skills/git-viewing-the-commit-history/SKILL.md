---
name: git-viewing-the-commit-history
description: "Viewing the Commit History playbook extracted from \"Pro Git\". Another really helpful filter is the -S option (colloquially referred to as Git’s “pickaxe” option), which takes a string and shows only those commits that changed the number of occurrences of that string. Use when the user asks about viewing the commit history, git log, show commits, log output, format, command, files; or mentions git log, git log --pretty, git clone, git log -p, git log --stat, git log --pretty --graph."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Viewing the Commit History"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "46-52"
---

# Viewing the Commit History

Another really helpful filter is the `-S` option (colloquially referred to as Git’s “pickaxe” option), which takes a string and shows only those commits that changed the number of occurrences of that string.

_Built from "Pro Git" (pages 46-52) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **viewing the commit history** (git log, show commits, log output, format, command).
- The user wants to run or understand `git log`.
- The user wants to run or understand `git log --pretty`.
- The user wants to run or understand `git clone`.
- The user wants to run or understand `git log -p`.
- The `oneline` value for this option prints each commit on a single line, which is useful if you’re looking at a lot of commits.
- The `--author` option allows you to filter on a specific author, and the `--grep` option lets you search for keywords in the commit messages.

## When NOT to use

- For searching, use the `git-searching` skill instead.
- For maintaining a project, use the `git-distributed-git-maintaining-a-project` skill instead.
- For contributing to a project, use the `git-distributed-git-contributing-to-a-project` skill instead.

## Key concepts

- One of the more helpful options is `-p` or `--patch`, which shows the difference (the patch output) introduced in each commit.
- As you can see, the `--stat` option prints below each commit entry a list of modified files, how many files were changed, and how many lines in those files were added and removed.
- In addition to output-formatting options, `git log` takes a number of useful limiting options; that is, options that let you show only a subset of commits.
- You’ve seen one such option already — the `-2` option, which displays only the last two commits.
- If you specify a directory or file name, you can limit the log output to commits that introduced a change to those files.
- `-<n>` Show only the last n commits.
- `--author` Only show commits in which the author entry matches the specified string.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Viewing the Commit History

**Goal:** The `oneline` value for this option prints each commit on a single line, which is useful if you’re looking at a lot of commits.

**Steps:**

1. To get the project, run:
   ```bash
   git clone https://github.com/schacon/simplegit-progit
   ```
2. When you run `git log` in this project, you should get output that looks something like this:
   ```bash
   git log
   ```
   Expected output (excerpt):
   ```text
   commit ca82a6dff817ec66f44342007202690a93763949
   Author: Scott Chacon <schacon@gee-mail.com>
   Date:   Mon Mar 17 21:52:11 2008 -0700
       Change version number
   ```
3. You can also limit the number of log entries displayed, such as using `-2` to show only the last two entries.
   ```bash
   git log -p -2
   ```
   Expected output (excerpt):
   ```text
   commit ca82a6dff817ec66f44342007202690a93763949
   Author: Scott Chacon <schacon@gee-mail.com>
   Date:   Mon Mar 17 21:52:11 2008 -0700
       Change version number
   ```
4. For example, if you want to see some abbreviated stats for each commit, you can use the `--stat` option:
   ```bash
   git log --stat
   ```
   Expected output (excerpt):
   ```text
   commit ca82a6dff817ec66f44342007202690a93763949
   Author: Scott Chacon <schacon@gee-mail.com>
   Date:   Mon Mar 17 21:52:11 2008 -0700
       Change version number
   ```
5. In addition, the `short`, `full`, and `fuller` values show the output in roughly the same format but with less or more information, respectively:
   ```bash
   git log --pretty=oneline
   ```
   Expected output (excerpt):
   ```text
   ca82a6dff817ec66f44342007202690a93763949 Change version number
   085bb3bcb608e1e8451d4b2432f8ecbe6306e7e7 Remove unnecessary test
   a11bef06a3f659402fe7563abf99ad00de2209e6 Initial commit
   ```
6. This is especially useful when you’re generating output for machine parsing — because you specify the format explicitly, you know it won’t change with updates to Git:
   ```bash
   git log --pretty=format:"%h - %an, %ar : %s"
   ```
   Expected output (excerpt):
   ```text
   ca82a6d - Scott Chacon, 6 years ago : Change version number
   085bb3b - Scott Chacon, 6 years ago : Remove unnecessary test
   a11bef0 - Scott Chacon, 6 years ago : Initial commit
   ```

_2 more step(s) in references/procedures.md._

**Verify:** run `git log --pretty=format:"%h %s" --graph` - expect something like:
```text
* 2d3acf9 Ignore errors from SIGCHLD on trap
*  5e3ee11 Merge branch 'master' of https://github.com/dustin/grit.git
|\
| * 420eac9 Add method for getting the current branch
* | 30e367c Timeout code and tests
```

### Limiting Log Output

**Goal:** The `--author` option allows you to filter on a specific author, and the `--grep` option lets you search for keywords in the commit messages.

**Steps:**

1. For example, this command gets the list of commits made in the last two weeks:
   ```bash
   git log --since=2.weeks
   ```
2. For instance, if you wanted to find the last commit that added or removed a reference to a specific function, you could call:
   ```bash
   git log -S function_name
   ```
3. This is always the last option and is generally preceded by double dashes (`--`) to separate the paths from the options:
   ```bash
   git log -- path/to/file
   ```
4. For example, if you want to see which commits modifying test files in the Git source code history were committed by Junio Hamano in the month of October 2008 and are not merge commits, you can run something like this:
   ```bash
   git log --pretty="%h - %s" --author='Junio C Hamano' --since="2008-10-01" \
   --before="2008-11-01" --no-merges -- t/
   ```
   Expected output (excerpt):
   ```text
   5610e3b - Fix testcase failure when extended attributes are in use
   acd3b9e - Enhance hold_lock_file_for_{update,append}() API
   f563754 - demonstrate breakage of detached checkout with symbolic link HEAD
   d1a43f2 - reset --hard/read-tree --reset -u: remove unmerged new paths
   ```

More procedures in [references/procedures.md](references/procedures.md):

- Viewing the Commit History

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git log` | The most basic and powerful tool to do this is the `git log` command. | `git log` |
| `git log --pretty` | Useful specifiers for `git log --pretty=format` lists some of the more useful specifiers that `format` takes. | `git log --pretty=oneline` |
| `git clone` | To get the project, run | `git clone https://github.com/schacon/simplegit-progit` |
| `git log -p` | You can also limit the number of log entries displayed, such as using `-2` to show only the last two entries. | `git log -p -2` |
| `git log --stat` | For example, if you want to see some abbreviated stats for each commit, you can use the `--stat` option | `git log --stat` |
| `git log --pretty --graph` | This option adds a nice little ASCII graph showing your branch and merge history | `git log --pretty=format:"%h %s" --graph` |
| `git log --since` | For example, this command gets the list of commits made in the last two weeks | `git log --since=2.weeks` |
| `git log -S` | For instance, if you wanted to find the last commit that added or removed a reference to a specific function, you could call | `git log -S function_name` |
| `git log --pretty --author` | For example, if you want to see which commits modifying test files in the Git source code history were committed by Junio Hamano in the month of October 2008 and are not merge commits, you can run something like this | `git log --pretty="%h - %s" --author='Junio C Hamano' --since="2008-10-01" \` |

## Decision guide

- `--abbrev-commit` Show only the first few characters of the SHA-1 checksum instead of all 40.
- `--relative-date` Display the date in a relative format (for example, “2 weeks ago”) instead of using the full date format.

## Troubleshooting

- **Note:** You can specify more than one instance of both the `--author` and `--grep` search criteria, which will limit the commit output to commits that match any of the `--author` patterns and any of the `--grep` patterns; however, adding the `--all-match` option further limits the output to just those commits that match all`--grep` patterns.
- **Tip:** Preventing the display of merge commits Depending on the workflow used in your repository, it’s possible that a sizable percentage of the commits in your log history are just merge commits, which typically aren’t very informative. To prevent the display of merge commits cluttering up your log history, simply add the `log` option `--no-merges`.

## Related skills

- `git-searching` - Searching
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-rewriting-history` - Rewriting History

## Source

"Pro Git", pages 46-52. Sections: Viewing the Commit History; Viewing the Commit History > Limiting Log Output.
