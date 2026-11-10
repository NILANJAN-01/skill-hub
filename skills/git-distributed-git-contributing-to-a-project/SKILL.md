---
name: git-distributed-git-contributing-to-a-project
description: "Contributing to a Project playbook extracted from \"Pro Git\". Because Git is very flexible, people can and do work together in many ways, and it’s problematic to describe how you should contribute — every project is a bit different. Use when the user asks about contributing to a project, jessica emails john, git project, topic branch, push, server, john fetches jessica; or mentions cd project, git push, git commit -am, git fetch, git checkout -b, git commit; or hits errors like \"! [rejected] master -> master (non-fast forward)\"."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Contributing to a Project"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "135-156"
---

# Contributing to a Project

Because Git is very flexible, people can and do work together in many ways, and it’s problematic to describe how you should contribute — every project is a bit different.

_Built from "Pro Git" (pages 135-156) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **contributing to a project** (jessica emails john, git project, topic branch, push, server).
- The user wants to run or understand `cd project`.
- The user wants to run or understand `git push`.
- The user wants to run or understand `git commit -am`.
- The user wants to run or understand `git fetch`.
- The user sees an error like `! [rejected]        master -> master (non-fast forward)`.

## When NOT to use

- For maintaining a project, use the `git-distributed-git-maintaining-a-project` skill instead.
- For contributing to a project, use the `git-github-contributing-to-a-project` skill instead.
- For git as a client, use the `git-as-a-client` skill instead.

## Key concepts

- The next variable is the workflow in use for the project.
- The workflow required in order to contribute to a project is much different if you have write access to the project than if you don’t.
- If you don’t have write access, how does the project prefer to accept contributed work?
- The Git project provides a document that lays out a number of good tips for creating commits from which to submit patches — you can read it in the Git source code in the `Documentation/SubmittingPatches` file.
- The Git project has well-formatted commit messages — try running `git log --no-merges` there to see what a nicely-formatted project-commit history looks like.
- Contributing to public projects is a bit different.
- Once your work has been pushed to your fork of the repository, you need to notify the maintainers of the original project that you have work you’d like them to merge.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git rebase origin/master`
  - `git push -f myfork featureA`
- **Note (from source):** You may want to use `rebase -i` to squash your work down to a single commit, or rearrange the work in the commits to make the patch easier for the maintainer to review — see Rewriting History for more information about interactive rebasing.
- Rewriting History describes a number of useful Git tricks for rewriting history and interactively staging files — use these tools to help craft a clean and understandable history before sending the work to someone else.
- On a project for which you’re not the maintainer, it’s generally easier to have a branch like `master` always track `origin/master` and to do your work in topic branches that you can easily discard if they’re rejected.
- This rewrites your history to now look like Commit history after `featureA` work.

## Procedures

### Commit Guidelines

**Goal:** The Git project requires that the more detailed explanation include your motivation for the change and contrast its implementation with previous behavior — this is a good guideline to follow.

**Steps:**

1. Write your commit message in the imperative: "Fix bug" and not "Fixed bug" or "Fixes bug." Here is a template you can follow, which we’ve lightly adapted from one originally written by Tim Pope:
   ```text
   Capitalized, short (50 chars or less) summary
   More detailed explanatory text, if necessary.  Wrap it to about 72
   characters or so.  In some contexts, the first line is treated as the
   subject of an email and the rest of the text as the body.  The blank
   line separating the summary from the body is critical (unless you omit
   the body entirely); tools like rebase will confuse you if you run the
   two together.
   Write your commit message in the imperative: "Fix bug" and not "Fixed bug"
   or "Fixes bug."  This convention matches up with commit messages generated
   by commands like git merge and git revert.
   Further paragraphs come after blank lines.
   - Bullet points are okay, too
   - Typically a hyphen or asterisk is used for the bullet, followed by a
     single space, with blank lines in between, but conventions vary here
   - Use a hanging indent
   ```

**If it fails:** This approach also makes it easier to pull out or revert one of the changesets if you need to later.

### Private Small Team

**Goal:** The simplest setup you’re likely to encounter is a private project with one or two other developers.

**Steps:**

1. The protocol messages have been replaced with `…` in these examples to shorten them somewhat.
   ```bash
   git clone john@githost:simplegit.git
   cd simplegit/
   vim lib/simplegit.rb
   git commit -am 'Remove invalid default value'
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'simplegit'...
   ...
   [master 738ee87] Remove invalid default value
    1 files changed, 1 insertions(+), 1 deletions(-)
   ```
2. The second developer, Jessica, does the same thing — clones the repository and commits a change:
   ```bash
   git clone jessica@githost:simplegit.git
   cd simplegit/
   vim TODO
   git commit -am 'Add reset task'
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'simplegit'...
   ...
   [master fbff5bc] Add reset task
    1 files changed, 1 insertions(+), 0 deletions(-)
   ```
3. Now, Jessica pushes her work to the server, which works just fine:
   ```bash
   git push origin master
   ```
   Expected output (excerpt):
   ```text
   ...
   To jessica@githost:simplegit.git
      1edee6b..fbff5bc  master -> master
   ```
4. Continuing with this example, shortly afterwards, John makes some changes, commits them to his local repository, and tries to push them to the same server:
   ```bash
   git push origin master
   ```
   Expected output (excerpt):
   ```text
   To john@githost:simplegit.git
    ! [rejected]        master -> master (non-fast forward)
   error: failed to push some refs to 'john@githost:simplegit.git'
   ```
5. As a first step, John fetches Jessica’s work (this only fetches Jessica’s upstream work, it does not yet merge it into John’s work):
   ```bash
   git fetch origin
   ```
   Expected output (excerpt):
   ```text
   ...
   From john@githost:simplegit
    + 049d078...fbff5bc master     -> origin/master
   ```
6. Now John can merge Jessica’s work that he fetched into his own local work:
   ```bash
   git merge origin/master
   ```
   Expected output (excerpt):
   ```text
   Merge made by the 'recursive' strategy.
    TODO |    1 +
    1 files changed, 1 insertions(+), 0 deletions(-)
   ```

_7 more step(s) in references/procedures.md._

**Verify:** run `git log --no-merges issue54..origin/master` - expect something like:
```text
commit 738ee872852dfaa9d6634e0dea7a324040193016
Author: John Smith <jsmith@example.com>
Date:   Fri May 29 16:01:27 2009 -0700
   Remove invalid default value
```

### Private Managed Team

**Goal:** Private Managed Team

**Steps:**

1. She creates a new branch for the feature and does some work on it there:
   ```bash
   git checkout -b featureA
   vim lib/simplegit.rb
   git commit -am 'Add limit to log function'
   ```
   Expected output (excerpt):
   ```text
   Switched to a new branch 'featureA'
   [featureA 3300904] Add limit to log function
    1 files changed, 1 insertions(+), 1 deletions(-)
   ```
2. Jessica doesn’t have push access to the `master` branch — only the integrators do — so she has to push to another branch in order to collaborate with John:
   ```bash
   git push -u origin featureA
   ```
   Expected output (excerpt):
   ```text
   ...
   To jessica@githost:simplegit.git
    * [new branch]      featureA -> featureA
   ```
3. To begin, she starts a new feature branch, basing it off the server’s `master` branch:
   ```bash
   git fetch origin
   git checkout -b featureB origin/master
   ```
   Expected output (excerpt):
   ```text
   Switched to a new branch 'featureB'
   ```
4. Now, Jessica makes a couple of commits on the `featureB` branch:
   ```bash
   vim lib/simplegit.rb
   git commit -am 'Make ls-tree function recursive'
   vim lib/simplegit.rb
   ```
   Expected output (excerpt):
   ```text
   [featureB e5b0fdc] Make ls-tree function recursive
    1 files changed, 1 insertions(+), 1 deletions(-)
   ```
5. Run:
   ```bash
   git commit -am 'Add ls-files'
   ```
   Expected output (excerpt):
   ```text
   [featureB 8512791] Add ls-files
    1 files changed, 5 insertions(+), 0 deletions(-)
   ```
6. Josie’s changes with `git fetch`:
   ```bash
   git fetch origin
   ```
   Expected output (excerpt):
   ```text
   ...
   From jessica@githost:simplegit
    * [new branch]      featureBee -> origin/featureBee
   ```

_8 more step(s) in references/procedures.md._

**Verify:** run `git log featureA..origin/featureA` - expect something like:
```text
commit aad881d154acdaeb2b6b18ea0e827ed8a6d671e6
Author: John Smith <jsmith@example.com>
Date:   Fri May 29 19:57:33 2009 -0700
    Increase log output to 30 from 25
```

### Forked Public Project

**Goal:** Contributing to public projects is a bit different.

**Steps:**

1. The sequence looks basically like this:
   ```bash
   git clone <url>
   cd project
   git checkout -b featureA
   git commit
   git commit
   ```
   Expected output (excerpt):
   ```text
     ... work ...
     ... work ...
   ```
2. You then need to add this repository URL as a new remote of your local repository; in this example, let’s call it `myfork`:
   ```bash
   git remote add myfork <url>
   ```
3. In any event, you can push your work with:
   ```bash
   git push -u myfork featureA
   ```
4. For instance, if Jessica wants to send John a pull request, and she’s done two commits on the topic branch she just pushed, she can run this:
   ```bash
   git request-pull origin/master myfork
   ```
   Expected output (excerpt):
   ```text
   The following changes since commit 1edee6b1d61823a2de3b09c160d7080b8d1b3a40:
   Jessica Smith (1):
           Create new function
   are available in the git repository at:
   ```
5. For example, if you want to submit a second topic of work to the project, don’t continue working on the topic branch you just pushed up — start over from the main repository’s `master` branch:
   ```bash
   git checkout -b featureB origin/master
   git commit
   git push myfork featureB
   git request-pull origin/master myfork
   git fetch origin
   ```
   Expected output (excerpt):
   ```text
     ... work ...
     ... email generated request pull to maintainer ...
   ```
6. In this case, you can try to rebase that branch on top of `origin/master`, resolve the conflicts for the maintainer, and then resubmit your changes:
   ```bash
   git checkout featureA
   git rebase origin/master
   git push -f myfork featureA
   ```

_1 more step(s) in references/procedures.md._

**If it fails:** For example, if you want to submit a second topic of work to the project, don’t continue working on the topic branch you just pushed up — start over from the main repository’s `master` branch:

### Public Project over Email

**Goal:** Many projects have established procedures for accepting patches — you’ll need to check the specific rules for each project, because they will differ.

**Steps:**

1. Instead of forking the project and pushing to your own writable version, you generate email versions of each commit series and email them to the developer mailing list:
   ```bash
   git checkout -b topicA
   git commit
   git commit
   ```
   Expected output (excerpt):
   ```text
     ... work ...
     ... work ...
   ```
2. The nice thing about this is that applying a patch from an email generated with `format-patch` preserves all the commit information properly.
   ```bash
   git format-patch -M origin/master
   ```
   Expected output (excerpt):
   ```text
   0001-add-limit-to-log-function.patch
   0002-increase-log-output-to-30-from-25.patch
   ```
3. The files end up looking like this:
   ```bash
   cat 0001-add-limit-to-log-function.patch
   ```
   Expected output (excerpt):
   ```text
   From 330090432754092d704da8e76ca5c05c198e71a8 Mon Sep 17 00:00:00 2001
   From: Jessica Smith <jessica@example.com>
   Date: Sun, 6 Apr 2008 10:17:23 -0700
   Subject: [PATCH 1/2] Add limit to log function
   ```
4. You can set each value separately with a series of `git config` commands, or you can add them manually, but in the end your config file should look something like this:
   ```ini
   [imap]
     folder = "[Gmail]/Drafts"
     host = imaps://imap.gmail.com
     user = user@gmail.com
     pass = YX]8g76G_2^sFbd
     port = 993
     sslverify = false
   ```
5. When that is set up, you can use `git imap-send` to place the patch series in the Drafts folder of the specified IMAP server:
   ```bash
   cat *.patch |git imap-send
   ```
   Expected output (excerpt):
   ```text
   Resolving imap.gmail.com... ok
   Connecting to [74.125.142.109]:993... ok
   Logging in...
   sending 2 messages
   ```
6. As before, you can set each value separately with a series of `git config` commands, or you can add them manually in the sendemail section in your `~/.gitconfig` file:
   ```ini
   [sendemail]
     smtpencryption = tls
     smtpserver = smtp.gmail.com
     smtpuser = user@gmail.com
     smtpserverport = 587
   ```

_3 more step(s) in references/procedures.md._

**Verify:** run `cat *.patch |git imap-send` - expect something like:
```text
Resolving imap.gmail.com... ok
Connecting to [74.125.142.109]:993... ok
Logging in...
sending 2 messages
100% (2/2) done
```

More procedures in [references/procedures.md](references/procedures.md):

- Private Small Team
- Private Managed Team
- Forked Public Project
- Public Project over Email

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git push` | Now, Jessica pushes her work to the server, which works just fine | `git push` |
| `git commit -am` | The protocol messages have been replaced with `…` in these examples to shorten them somewhat. | `git commit -am 'Add ls-files'` |
| `git fetch` | Again, Jessica runs a simple `git fetch` to fetch all new content from the server, including (of course) John’s latest work | `git fetch origin` |
| `git checkout -b` | She creates a new branch for the feature and does some work on it there | `git checkout -b topicA` |
| `git commit` | The sequence looks basically like this | `git commit` |
| `git merge` | Assuming Jessica is still on her checked-out `featureB` branch, she can now merge Josie’s work into that branch with `git merge` | `git merge issue54` |
| `git clone` | The protocol messages have been replaced with `…` in these examples to shorten them somewhat. | `git clone <url>` |
| `git checkout` | First (having committed all of the work on her `issue54` topic branch), Jessica switches back to her `master` branch in preparation for integrating all this work | `git checkout master` |
| `git push -u` | Jessica doesn’t have push access to the `master` branch — only the integrators do — so she has to push to another branch in order to collaborate with John | `git push -u origin featureA` |
| `git request-pull` | The `git request-pull` command takes the base branch into which you want your topic branch pulled and the Git repository URL you want them to pull from, and produces a summary of all the changes you’re asking to be pulled. | `git request-pull origin/master myfork` |
| `git log --no-merges` | The Git project has well-formatted commit messages — try running `git log --no-merges` there to see what a nicely-formatted project-commit history looks like. | `git log --no-merges issue54..origin/master` |
| `git log` | The Git project has well-formatted commit messages — try running `git log --no-merges` there to see what a nicely-formatted project-commit history looks like. | `git log featureA..origin/featureA` |
| `git remote` | You then need to add this repository URL as a new remote of your local repository; in this example, let’s call it `myfork` | `git remote add myfork <url>` |
| `git rebase` | In this case, you can try to rebase that branch on top of `origin/master`, resolve the conflicts for the maintainer, and then resubmit your changes | `git rebase origin/master` |
| `git push -f` | In this case, you can try to rebase that branch on top of `origin/master`, resolve the conflicts for the maintainer, and then resubmit your changes | `git push -f myfork featureA` |
| `git merge --squash` | You start a new branch based off the current `origin/master` branch, squash the `featureB` changes there, resolve any conflicts, make the implementation change, and then push that as a new branch | `git merge --squash featureB` |
| `git format-patch -M` | The nice thing about this is that applying a patch from an email generated with `format-patch` preserves all the commit information properly. | `git format-patch -M origin/master` |
| `git send-email` | After this is done, you can use `git send-email` to send your patches | `git send-email *.patch` |

## Decision guide

- If you don’t have write access, how does the project prefer to accept contributed work?
- All these questions can affect how you contribute effectively to a project and what workflows are preferred or available to you.
- The next section deals with projects that prefer to accept contributed patches via email.
- If your IMAP server doesn’t use SSL, the last two lines probably aren’t necessary, and the host value will be `imap://` instead of `imaps://`.

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

## Source

"Pro Git", pages 135-156. Sections: Contributing to a Project; Contributing to a Project > Commit Guidelines; Contributing to a Project > Private Small Team; Contributing to a Project > Private Managed Team; Contributing to a Project > Forked Public Project; Contributing to a Project > Public Project over Email; Contributing to a Project > Summary.
