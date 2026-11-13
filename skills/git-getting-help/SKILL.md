---
name: git-getting-help
description: "Look up git docs with git help, --help and man. Use when asked how to find a git command's options."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Getting Help"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "30-31"
---

# Getting Help

These channels are regularly filled with hundreds of people who are all very knowledgeable about Git and are often willing to help.

_Built from "Pro Git" (pages 30-31) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **getting help** (comprehensive manual page, git config, git commands, manpage, offline).
- The user wants to run or understand `git help`.
- The user wants to run or understand `git --help`.
- The user wants to run or understand `man`.
- The user wants to run or understand `git add -h`.
- The user sees an error like `errors`.

## When NOT to use

- For setup and config, use the `git-setup-and-config` skill instead.
- For git configuration, use the `git-configuration` skill instead.

## Key concepts

- These commands are nice because you can access them anywhere, even offline.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Getting Help

**Goal:** These channels are regularly filled with hundreds of people who are all very knowledgeable about Git and are often willing to help.

**Steps:**

1. If you ever need help while using Git, there are three equivalent ways to get the comprehensive manual page (manpage) help for any of the Git commands:
   ```bash
   git help <verb>
   git <verb> --help
   man git-<verb>
   ```
2. For example, you can get the manpage help for the `git config` command by running this:
   ```bash
   git help config
   ```
3. In addition, if you don’t need the full-blown manpage help, but just need a quick refresher on the available options for a Git command, you can ask for the more concise “help” output with the `-h` option, as in:
   ```bash
   git add -h
   ```
   Expected output (excerpt):
   ```text
   usage: git add [<options>] [--] <pathspec>...
       -n, --dry-run               dry run
       -v, --verbose               be verbose
       -i, --interactive           interactive picking
   ```
4. Run:
   ```text
       --ignore-missing            check if - even missing - files are ignored in dry run
       --sparse                    allow updating entries outside of the sparse-checkout
   cone
       --chmod (+|-)x              override the executable bit of the listed files
       --pathspec-from-file <file> read pathspec from file
       --pathspec-file-nul         with --pathspec-from-file, pathspec elements are
   separated with NUL character
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git help` | If you ever need help while using Git, there are three equivalent ways to get the comprehensive manual page (manpage) help for any of the Git commands | `git help <verb>` |
| `git --help` | If you ever need help while using Git, there are three equivalent ways to get the comprehensive manual page (manpage) help for any of the Git commands | `git <verb> --help` |
| `man` | These commands are nice because you can access them anywhere, even offline. | `man git-<verb>` |
| `git add -h` | In addition, if you don’t need the full-blown manpage help, but just need a quick refresher on the available options for a Git command, you can ask for the more concise “help” output with the `-h` option, as in | `git add -h` |

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `errors` | See references/source-text.md for this section. |


## Related skills

- `git-setup-and-config` - Setup and Config
- `git-configuration` - Git Configuration

## Source

"Pro Git", pages 30-31. Sections: Getting Help.
