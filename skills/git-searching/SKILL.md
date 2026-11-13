---
name: git-searching
description: "Search code and history: git grep, log -S, log -G, log -L. Use when you need to find where something is or when it changed."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Searching"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "245-249"
---

# Searching

Another fairly advanced log search that is insanely useful is the line history search.

_Built from "Pro Git" (pages 245-249) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **searching** (git grep, search string, git log, option, line).
- The user wants to run or understand `git grep -n`.
- The user wants to run or understand `git grep --count`.
- The user wants to run or understand `git grep -p`.
- The user wants to run or understand `git grep --break --heading`.
- Git ships with a command called `grep` that allows you to easily search through any committed tree, the working directory, or even the index for a string or regular expression.
- If you need to be more specific, you can provide a regular expression to search for with the `-G` option.

## When NOT to use

- For viewing the commit history, use the `git-viewing-the-commit-history` skill instead.
- For debugging with git, use the `git-debugging-with-git` skill instead.
- For migrating to git, use the `git-migrating-to-git` skill instead.

## Key concepts

- Git ships with a command called `grep` that allows you to easily search through any committed tree, the working directory, or even the index for a string or regular expression.
- For the examples that follow, we’ll search through the source code for Git itself.
- In addition to the basic search shown above, `git grep` supports a plethora of other interesting options.
- You can also search for complex combinations of strings with the `--and` flag, which ensures that multiple matches must occur in the same line of text.
- The `git grep` command has a few advantages over normal searching commands like `grep` and `ack`.
- The first is that it’s really fast, the second is that you can search through any tree in Git, not just the working directory.
- If you need to be more specific, you can provide a regular expression to search for with the `-G` option.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Git Grep

**Goal:** Git ships with a command called `grep` that allows you to easily search through any committed tree, the working directory, or even the index for a string or regular expression.

**Steps:**

1. As a first variation, you can use either of the `-n` or `--line-number` options to print out the line numbers where Git has found matches:
   ```bash
   git grep -n gmtime_r
   ```
   Expected output (excerpt):
   ```text
   compat/gmtime.c:3:#undef gmtime_r
   compat/gmtime.c:8:      return git_gmtime_r(timep, &result);
   compat/gmtime.c:11:struct tm *git_gmtime_r(const time_t *timep, struct tm *result)
   compat/gmtime.c:16:     ret = gmtime_r(timep, result);
   ```
2. For instance, instead of printing all of the matches, you can ask `git grep` to summarize the output by showing you only which files contained the search string and how many matches there were in each file with the `-c` or `--count` option:
   ```bash
   git grep --count gmtime_r
   ```
   Expected output (excerpt):
   ```text
   compat/gmtime.c:4
   compat/mingw.c:1
   compat/mingw.h:1
   date.c:3
   ```
3. If you’re interested in the context of a search string, you can display the enclosing method or function for each matching string with either of the `-p` or `--show-function` options:
   ```bash
   git grep -p gmtime_r *.c
   ```
   Expected output (excerpt):
   ```text
   date.c=static int match_multi_number(timestamp_t num, char c, const char *date,
   date.c:         if (gmtime_r(&now, &now_tm))
   date.c=static int match_digit(const char *date, struct tm *tm, int *offset, int
   *tm_gmt)
   ```
4. Run:
   ```text
   date.c:         /* gmtime_r() in match_digit() may have clobbered it */
   ```
5. For instance, let’s look for any lines that define a constant whose name contains either of the substrings “LINK” or “BUF_MAX”, specifically in an older version of the Git codebase represented by the tag `v1.8.0` (we’ll throw in the `--break` and `--heading` options which help split up the output into a more readable format):
   ```bash
   git grep --break --heading \
   -n -e '#define' --and \( -e LINK -e BUF_MAX \) v1.8.0
   ```
   Expected output (excerpt):
   ```text
   v1.8.0:builtin/index-pack.c
   62:#define FLAG_LINK (1u<<20)
   v1.8.0:cache.h
   73:#define S_IFGITLINK  0160000
   ```

### Git Log Searching

**Goal:** If you need to be more specific, you can provide a regular expression to search for with the `-G` option.

**Steps:**

1. If, for example, we want to find out when the `ZLIB_BUF_MAX` constant was originally introduced, we can use the `-S` option (colloquially referred to as the Git “pickaxe” option) to tell Git to show us only those commits that changed the number of occurrences of that string.
   ```bash
   git log -S ZLIB_BUF_MAX --oneline
   ```
   Expected output (excerpt):
   ```text
   e01503b zlib: allow feeding more than 4GB in one go
   ef49a7a zlib: zlib can only process 4GB at a time
   ```
2. This will try to figure out what the bounds of that function are and then look through the history and show us every change that was made to the function as a series of patches back to when the function was first created.
   ```bash
   git log -L :git_deflate_bound:zlib.c
   ```
   Expected output (excerpt):
   ```text
   commit ef49a7a0126d64359c974b4b3b71d7ad42ee3bca
   Author: Junio C Hamano <gitster@pobox.com>
   Date:   Fri Jun 10 11:52:15 2011 -0700
       zlib: zlib can only process 4GB at a time
   ```
3. Run:
   ```text
   @@ -81,0 +85,5 @@
   +unsigned long git_deflate_bound(z_streamp strm, unsigned long size)
   +{
   +       return deflateBound(strm, size);
   +}
   +
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git grep -n` | As a first variation, you can use either of the `-n` or `--line-number` options to print out the line numbers where Git has found matches | `git grep -n gmtime_r` |
| `git grep --count` | For instance, instead of printing all of the matches, you can ask `git grep` to summarize the output by showing you only which files contained the search string and how many matches there were in each file with the `-c` or `--count` option | `git grep --count gmtime_r` |
| `git grep -p` | If you’re interested in the context of a search string, you can display the enclosing method or function for each matching string with either of the `-p` or `--show-function` options | `git grep -p gmtime_r *.c` |
| `git grep --break --heading` | For instance, let’s look for any lines that define a constant whose name contains either of the substrings “LINK” or “BUF_MAX”, specifically in an older version of the Git codebase represented by the tag `v1.8.0` (we’ll throw in the `--break` and `--heading` options which help split up the output into a more readable format) | `git grep --break --heading \` |
| `git log -S --oneline` | If, for example, we want to find out when the `ZLIB_BUF_MAX` constant was originally introduced, we can use the `-S` option (colloquially referred to as the Git “pickaxe” option) to tell Git to show us only those commits that changed the number of occurrences of that string. | `git log -S ZLIB_BUF_MAX --oneline` |
| `git log -L` | For example, this would have done the same thing as the example above: `git log -L '/unsigned long git_deflate_bound/',/^}/:zlib.c`. | `git log -L :git_deflate_bound:zlib.c` |

## Related skills

- `git-viewing-the-commit-history` - Viewing the Commit History
- `git-debugging-with-git` - Debugging with Git
- `git-migrating-to-git` - Migrating to Git
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project

## Source

"Pro Git", pages 245-249. Sections: Searching; Searching > Git Grep; Searching > Git Log Searching.
