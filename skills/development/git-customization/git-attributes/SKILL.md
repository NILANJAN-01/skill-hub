---
name: git-attributes
description: "Set per-file git behaviour in .gitattributes: binary files, diff filters, export-ignore. Use when handling .gitattributes questions."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git Attributes"
  category: git-customization
  source: "Pro Git, 2nd edition"
  pages: "352-360"
---

# Git Attributes

These path-specific settings are called Git attributes and are set either in a `.gitattributes` file in one of your directories (normally the root of your project) or in the `.git/info/attributes` file if you don’t want the attributes file committed with your project.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git checkout -- test.txt`
- Don’t forget to `chmod a+x` that file.
- You have to be careful, though, because the `.gitattributes` file is committed and passed around with the project, but the driver (in this case, `dater`) isn’t, so it won’t work everywhere.

## Commands

- `git config`: `git config diff.word.textconv docx2txt`
- `git config --global`: `git config --global merge.ours.driver true`
- `git diff`
- `git checkout`: `git checkout -- test.txt`
- `git add`: `git add LAST_COMMIT .gitattributes`
- `git commit -am`: `git commit -am 'adding LAST_COMMIT file for archives'`
- `git archive`: tar xfO - LAST_COMMIT`
- `git config -pe`: `git config filter.dater.clean 'perl -pe "s/\\\$Date[^\\\$]*\\\$/\\\$Date\\\$/"'`
- `git commit -m`: `git commit -m "Test date expansion in Git"`
- `git merge`: `git merge topic`

## Related skills

- `git-configuration` - Git Configuration
- `git-advanced-merging` - Advanced Merging
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-distributed-git-maintaining-a-project` - Maintaining a Project

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 352-360, CC BY-NC-SA 3.0._
