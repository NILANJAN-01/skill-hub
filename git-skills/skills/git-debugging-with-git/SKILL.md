---
name: git-debugging-with-git
description: "Debugging with Git playbook extracted from \"Pro Git\". If you track down a bug in your code and want to know when it was introduced and why, file annotation is often your best tool. Use when the user asks about debugging with git, git bisect, git blame, bad commit, line, good, commits; or mentions git bisect, git blame -L, git blame -C -L."
---

# Debugging with Git

If you track down a bug in your code and want to know when it was introduced and why, file annotation is often your best tool.

_Built from "Pro Git" (pages 301-304) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **debugging with git** (git bisect, git blame, bad commit, line, good).
- The user wants to run or understand `git bisect`.
- The user wants to run or understand `git blame -L`.
- The user wants to run or understand `git blame -C -L`.

## When NOT to use

- For searching, use the `git-searching` skill instead.
- For git as a client, use the `git-as-a-client` skill instead.
- For advanced merging, use the `git-advanced-merging` skill instead.

## Key concepts

- It shows you what commit was the last to modify each line of any file.
- Notice that the first field is the partial SHA-1 of the commit that last modified that line.
- Normally, you get as the original commit the commit where you copied the code over, because that is the first time you touched those lines in this file.
- Git tells you the original commit where you wrote those lines, even if it was in another file.
- If you don’t know what is breaking, and there have been dozens or hundreds of commits since the last state where you know the code worked, you’ll likely turn to `git bisect` for help.
- Git figured out that about 12 commits came between the commit you marked as the last good commit (v1.0) and the current bad version, and it checked out the middle one for you.
- This is a powerful tool that can help you check hundreds of commits for an introduced bug in minutes.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### File Annotation

**Goal:** File Annotation

**Steps:**

1. The following example uses `git blame` to determine which commit and committer was responsible for lines in the top-level Linux kernel `Makefile` and, further, uses the `-L` option to restrict the output of the annotation to lines 69 through 82 of that file:
   ```bash
   git blame -L 69,82 Makefile
   ```
   Expected output (excerpt):
   ```text
   b8b0618cf6fab (Cheng Renquan  2009-05-26 16:03:07 +0800 69) ifeq ("$(origin V)",
   "command line")
   b8b0618cf6fab (Cheng Renquan  2009-05-26 16:03:07 +0800 70)   KBUILD_VERBOSE = $(V)
   ^1da177e4c3f4 (Linus Torvalds 2005-04-16 15:20:36 -0700 71) endif
   ```
2. By blaming `GITPackUpload.m` with the `-C` option, you can see where sections of the code originally came from:
   ```bash
   git blame -C -L 141,153 GITPackUpload.m
   ```
   Expected output (excerpt):
   ```text
   f344f58d GITServerHandler.m (Scott 2009-01-04 141)
   f344f58d GITServerHandler.m (Scott 2009-01-04 142) - (void) gatherObjectShasFromC
   f344f58d GITServerHandler.m (Scott 2009-01-04 143) {
   70befddd GITServerHandler.m (Scott 2009-03-22 144)         //NSLog(@"GATHER COMMI
   ```

### Binary Search

**Goal:** Binary Search

**Steps:**

1. Then, you must tell bisect when the last known good state was, using `git bisect good <good_commit>`:
   ```bash
   git bisect start
   git bisect bad
   git bisect good v1.0
   ```
   Expected output (excerpt):
   ```text
   Bisecting: 6 revisions left to test after this
   [ecb6e1bc347ccecc5f9350d878ce677feb13d3b2] Error handling on repo
   ```
2. It turns out there is no issue here, and you tell Git that by typing `git bisectgood` and continue your journey:
   ```bash
   git bisect good
   ```
   Expected output (excerpt):
   ```text
   Bisecting: 3 revisions left to test after this
   [b047b02ea83310a70fd603dc8cd7a6cd13d15c04] Secure this thing
   ```
3. You run your test again and find that this commit is broken, so you tell Git that with `git bisect bad`:
   ```bash
   git bisect bad
   ```
   Expected output (excerpt):
   ```text
   Bisecting: 1 revisions left to test after this
   [f71ce38690acf49c1f3c9bea38e09d82a5ce6014] Drop exceptions table
   ```
4. It tells you the SHA-1 of the first bad commit and shows some of the commit information and which files were modified in that commit so you can figure out what happened that may have introduced this bug:
   ```bash
   git bisect good
   ```
   Expected output (excerpt):
   ```text
   b047b02ea83310a70fd603dc8cd7a6cd13d15c04 is first bad commit
   commit b047b02ea83310a70fd603dc8cd7a6cd13d15c04
   Author: PJ Hyett <pjhyett@example.com>
   Date:   Tue Jan 27 14:48:32 2009 -0800
   ```
5. When you’re finished, you should run `git bisect reset` to reset your HEAD to where you were before you started, or you’ll end up in a weird state:
   ```bash
   git bisect reset
   ```
6. You can do this by listing them with the `bisect start` command if you want, listing the known bad commit first and the known good commit second:
   ```bash
   git bisect start HEAD v1.0
   git bisect run test-error.sh
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git bisect` | Then, you must tell bisect when the last known good state was, using `git bisect good <good_commit>` | `git bisect bad` |
| `git blame -L` | The following example uses `git blame` to determine which commit and committer was responsible for lines in the top-level Linux kernel `Makefile` and, further, uses the `-L` option to restrict the output of the annotation to lines 69 through 82 of that file | `git blame -L 69,82 Makefile` |
| `git blame -C -L` | By blaming `GITPackUpload.m` with the `-C` option, you can see where sections of the code originally came from | `git blame -C -L 141,153 GITPackUpload.m` |

## Decision guide

- If you track down a bug in your code and want to know when it was introduced and why, file annotation is often your best tool.

## Related skills

- `git-searching` - Searching
- `git-as-a-client` - Git as a Client
- `git-advanced-merging` - Advanced Merging
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository

## Source

"Pro Git", pages 301-304. Sections: Debugging with Git; Debugging with Git > File Annotation; Debugging with Git > Binary Search.
