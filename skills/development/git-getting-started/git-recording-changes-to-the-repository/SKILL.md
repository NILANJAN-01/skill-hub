---
name: git-recording-changes-to-the-repository
description: "Everyday git: status, add, .gitignore, diff, commit, rm, mv. Use when you need to stage, commit, ignore or rename files."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Recording Changes to the Repository"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "34-46"
---

# Recording Changes to the Repository

The `CONTRIBUTING.md` file appears under a section named “Changes not staged for commit” — which means that a file that is tracked has been modified in the working directory but not yet staged.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- This is convenient, but be careful; sometimes this flag will cause you to include unwanted changes.
- If you modified the file or had already added it to the staging area, you must force the removal with the `-f` option.

## Commands

- `git status`
- `git add`: `git add README`
- `git rm`: `git rm \*~`
- `git diff`
- `git mv`: `git mv README.md README`
- `git status -s`
- `git diff --staged`
- `git diff --cached`
- `git commit`
- `git commit -m`: `git commit -m "Story 182: fix benchmarks for speed"`
- `git commit -a -m`: `git commit -a -m 'Add new benchmarks'`
- `git rm --cached`: `git rm --cached README`

## Troubleshooting

- **Note:** GitHub changed the default branch name from `master` to `main` in mid-2020, and other Git hosts followed suit. So you may find that the default branch name in some newly created repositories is `main` and not `master`. In addition, the default branch name can be changed (as you have seen in Your default branch name), so you may see a different name for the default branch.
- **Tip:** GitHub maintains a fairly comprehensive list of good `.gitignore` file examples for dozens of projects and languages at https://github.com/github/gitignore if you want a starting point for your project. In the simple case, a repository might have a single `.gitignore` file in its root directory, which applies recursively to the entire repository. However, it is also possible to have additional `.gitignore` files in subdirectories. The rules in these nested `.gitignore` files apply only to the files under the directory where they are located. The Linux kernel source repository has 206 `.gitignore` files.

## Related skills

- `git-undoing-things` - Undoing Things
- `git-interactive-staging` - Interactive Staging
- `git-basic-snapshotting` - Basic Snapshotting
- `git-stashing-and-cleaning` - Stashing and Cleaning

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 34-46, CC BY-NC-SA 3.0._
