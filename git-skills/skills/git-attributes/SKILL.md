---
name: git-attributes
description: "Git Attributes playbook extracted from \"Pro Git\". These path-specific settings are called Git attributes and are set either in a .gitattributes file in one of your directories (normally the root of your project) or in the .git/info/attributes file if you don’t want the attributes file committed with... Use when the user asks about git attributes, git attributes, git diff, git archive, date, git log, merge; or mentions echo, git config, cat, git config --global, git diff, rm."
---

# Git Attributes

These path-specific settings are called Git attributes and are set either in a `.gitattributes` file in one of your directories (normally the root of your project) or in the `.git/info/attributes` file if you don’t want the attributes file committed with your project.

_Built from "Pro Git" (pages 352-360) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **git attributes** (git attributes, git diff, git archive, date, git log).
- The user wants to run or understand `echo`.
- The user wants to run or understand `git config`.
- The user wants to run or understand `cat`.
- The user wants to run or understand `git config --global`.
- One cool trick for which you can use Git attributes is telling Git which files are binary (in cases it otherwise may not be able to figure out) and giving Git special instructions about how to handle those files.
- Git attribute data also allows you to do some interesting things when exporting an archive of your project.

## When NOT to use

- If there is a subdirectory or file that you don’t want to include in your archive file but that you do want checked into your project, you can determine those files via the `export-ignore` attribute.
- For git configuration, use the `git-configuration` skill instead.
- For advanced merging, use the `git-advanced-merging` skill instead.
- For recording changes to the repository, use the `git-recording-changes-to-the-repository` skill instead.

## Key concepts

- Using attributes, you can do things like specify separate merge strategies for individual files or directories in your project, tell Git how to diff non-text files, or have Git filter content before you check it into or out of Git.
- One cool trick for which you can use Git attributes is telling Git which files are binary (in cases it otherwise may not be able to figure out) and giving Git special instructions about how to handle those files.
- You can also use the Git attributes functionality to effectively diff binary files.
- If you set this attribute on a file or set of files, then the next time you check out that branch, Git will replace that field with the SHA-1 of the blob.
- Git attribute data also allows you to do some interesting things when exporting an archive of your project.
- You can also use Git attributes to tell Git to use different merge strategies for specific files in your project.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git checkout -- test.txt`
- Don’t forget to `chmod a+x` that file.
- You have to be careful, though, because the `.gitattributes` file is committed and passed around with the project, but the driver (in this case, `dater`) isn’t, so it won’t work everywhere.

## Procedures

### Binary Files

**Goal:** One cool trick for which you can use Git attributes is telling Git which files are binary (in cases it otherwise may not be able to figure out) and giving Git special instructions about how to handle those files.

**Steps:**

1. To tell Git to treat all `pbxproj` files as binary data, add the following line to your `.gitattributes` file:
   ```text
   *.pbxproj binary
   ```
2. If you run `git diff` normally, you only see something like this:
   ```bash
   git diff
   ```
   Expected output (excerpt):
   ```text
   diff --git a/chapter1.docx b/chapter1.docx
   index 88839c4..4afcb7c 100644
   Binary files a/chapter1.docx and b/chapter1.docx differ
   ```
3. Put the following line in your `.gitattributes` file:
   ```text
   *.docx diff=word
   ```
4. Create a file that’s somewhere in your path called `docx2txt`, and add these contents:
   ```bash
   #!/bin/bash
   docx2txt.pl "$1" -
   ```
5. Finally, you can configure Git to use this script:
   ```bash
   git config diff.word.textconv docx2txt
   ```
6. Here’s what `git diff` shows:
   ```bash
   git diff
   ```
   Expected output (excerpt):
   ```text
   diff --git a/chapter1.docx b/chapter1.docx
   index 0b013ca..ba25db5 100644
   --- a/chapter1.docx
   +++ b/chapter1.docx
   ```

_3 more step(s) in references/procedures.md._

**Verify:** run `git diff` - expect something like:
```text
diff --git a/chapter1.docx b/chapter1.docx
index 0b013ca..ba25db5 100644
--- a/chapter1.docx
+++ b/chapter1.docx
@@ -2,6 +2,7 @@
 This chapter will be about getting started with Git. We will begin at the beginning
```

**If it fails:** Now, Git won’t try to convert or fix CRLF issues; nor will it try to compute or print a diff for changes in this file when you run `git show` or `git diff` on your project.

### Keyword Expansion

**Goal:** Git attributes offers you two ways to do this.

**Steps:**

1. Put the following line in your `.gitattributes` file:
   ```text
   *.txt ident
   ```
2. Add an `$Id$` reference to a test file:
   ```bash
   echo '$Id$' > test.txt
   ```
3. The next time you check out this file, Git injects the SHA-1 of the blob:
   ```bash
   rm test.txt
   git checkout -- test.txt
   cat test.txt
   ```
   Expected output (excerpt):
   ```text
   $Id: 42812b7653c7b88933f8a9d6cad0ca16714b9bb3 $
   ```
4. You can set it up by setting the filter attribute in your `.gitattributes` file to filter `\*.c` files with the “indent” filter:
   ```text
   *.c filter=indent
   ```
5. Then, tell Git what the “indent” filter does on smudge and clean:
   ```bash
   git config --global filter.indent.clean indent
   git config --global filter.indent.smudge cat
   ```
6. Here is a small Ruby script that does that:
   ```ruby
   #! /usr/bin/env ruby
   data = STDIN.read
   last_date = `git log --pretty=format:"%ad" -1`
   puts data.gsub('$Date$', '$Date: ' + last_date.to_s + '$')
   ```

_3 more step(s) in references/procedures.md._

**If it fails:** This Perl snippet strips out anything it sees in a `$Date$` string, to get back to where you started.

### Exporting Your Repository

**Goal:** Git attribute data also allows you to do some interesting things when exporting an archive of your project.

**Steps:**

1. You can add the following line to your Git attributes file:
   ```text
   test/ export-ignore
   ```
2. For instance, if you want to include a file named `LAST_COMMIT` in your project, and have metadata about the last commit automatically injected into it when `git archive` runs, you can for example set up your `.gitattributes` and `LAST_COMMIT` files like this:
   ```bash
   echo 'Last commit date: $Format:%cd by %aN$' > LAST_COMMIT
   git add LAST_COMMIT .gitattributes
   git commit -am 'adding LAST_COMMIT file for archives'
   ```
3. When you run `git archive`, the contents of the archived file will look like this:
   ```bash
   git archive HEAD | tar xCf ../deployment-testing -
   cat ../deployment-testing/LAST_COMMIT
   ```
   Expected output (excerpt):
   ```text
   Last commit date: Tue Apr 21 08:38:48 2009 -0700 by Scott Chacon
   ```
4. The substitutions can include for example the commit message and any `git notes`, and `git log` can do simple word wrapping:
   ```bash
   echo '$Format:Last commit: %h by %aN at %cd%n%+w(76,6,9)%B$' > LAST_COMMIT
   git commit -am 'export-subst uses git log'\''s custom formatter
   git archive @ | tar xfO - LAST_COMMIT
   ```
   Expected output (excerpt):
   ```text
   git archive uses git log'\''s `pretty=format:` processor
   directly, and strips the surrounding `$Format:` and `$`
   markup from the output.
   '
   ```

### Merge Strategies

**Goal:** You can also use Git attributes to tell Git to use different merge strategies for specific files in your project.

**Steps:**

1. You can set up an attribute like this:
   ```text
   database.xml merge=ours
   ```
2. And then define a dummy `ours` merge strategy with:
   ```bash
   git config --global merge.ours.driver true
   ```
3. If you merge in the other branch, instead of having merge conflicts with the `database.xml` file, you see something like this:
   ```bash
   git merge topic
   ```
   Expected output (excerpt):
   ```text
   Auto-merging database.xml
   Merge made by recursive.
   ```

More procedures in [references/procedures.md](references/procedures.md):

- Binary Files
- Keyword Expansion

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git config` | Finally, you can configure Git to use this script | `git config diff.word.textconv docx2txt` |
| `git config --global` | Then, tell Git what the “indent” filter does on smudge and clean | `git config --global merge.ours.driver true` |
| `git diff` | If you run `git diff` normally, you only see something like this | `git diff` |
| `git checkout` | The next time you check out this file, Git injects the SHA-1 of the blob | `git checkout -- test.txt` |
| `git add` | If you commit those changes and check out the file again, you see the keyword properly substituted | `git add LAST_COMMIT .gitattributes` |
| `git commit -am` | For instance, if you want to include a file named `LAST_COMMIT` in your project, and have metadata about the last commit automatically injected into it when `git archive` runs, you can for example set up your `.gitattributes` and `LAST_COMMIT` files like this | `git commit -am 'adding LAST_COMMIT file for archives'` |
| `git archive` | For instance, if you want to include a file named `LAST_COMMIT` in your project, and have metadata about the last commit automatically injected into it when `git archive` runs, you can for example set up your `.gitattributes` and `LAST_COMMIT` files like this | `git archive @ \| tar xfO - LAST_COMMIT` |
| `git config -pe` | You’ll use a Perl expression to clean that up on commit | `git config filter.dater.clean 'perl -pe "s/\\\$Date[^\\\$]*\\\$/\\\$Date\\\$/"'` |
| `git commit -m` | If you commit those changes and check out the file again, you see the keyword properly substituted | `git commit -m "Test date expansion in Git"` |
| `git merge` | If you merge in the other branch, instead of having merge conflicts with the `database.xml` file, you see something like this | `git merge topic` |

## Decision guide

- When you design these filters, they should be able to fail gracefully and have the project still work properly.

## Related skills

- `git-configuration` - Git Configuration
- `git-advanced-merging` - Advanced Merging
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-distributed-git-maintaining-a-project` - Maintaining a Project

## Source

"Pro Git", pages 352-360. Sections: Git Attributes; Git Attributes > Binary Files; Git Attributes > Keyword Expansion; Git Attributes > Exporting Your Repository; Git Attributes > Merge Strategies.
