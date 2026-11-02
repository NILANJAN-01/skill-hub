# More procedures: Contributing to a Project

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
7. At this point, John might want to test this new code to make sure none of Jessica’s work affects any of his and, as long as everything seems fine, he can finally push the new merged work up to the server:
   ```bash
   git push origin master
   ```
   Expected output (excerpt):
   ```text
   ...
   To john@githost:simplegit.git
      fbff5bc..72bbc59  master -> master
   ```
8. Suddenly, Jessica learns that John has pushed some new work to the server and she wants to take a look at it, so she can fetch all new content from the server that she does not yet have with:
   ```bash
   git fetch origin
   ```
   Expected output (excerpt):
   ```text
   ...
   From jessica@githost:simplegit
      fbff5bc..72bbc59  master     -> origin/master
   ```
9. She runs `git log` to find out:
   ```bash
   git log --no-merges issue54..origin/master
   ```
   Expected output (excerpt):
   ```text
   commit 738ee872852dfaa9d6634e0dea7a324040193016
   Author: John Smith <jsmith@example.com>
   Date:   Fri May 29 16:01:27 2009 -0700
      Remove invalid default value
   ```
10. First (having committed all of the work on her `issue54` topic branch), Jessica switches back to her `master` branch in preparation for integrating all this work:
   ```bash
   git checkout master
   ```
   Expected output (excerpt):
   ```text
   Switched to branch 'master'
   Your branch is behind 'origin/master' by 2 commits, and can be fast-forwarded.
   ```
11. She chooses to merge the `issue54` branch first:
   ```bash
   git merge issue54
   ```
   Expected output (excerpt):
   ```text
   Updating fbff5bc..4af4298
   Fast forward
    README           |    1 +
    lib/simplegit.rb |    6 +++++-
   ```
12. Jessica now completes the local merging process by merging John’s earlier fetched work that is sitting in the `origin/master` branch:
   ```bash
   git merge origin/master
   ```
   Expected output (excerpt):
   ```text
   Auto-merging lib/simplegit.rb
   Merge made by the 'recursive' strategy.
    lib/simplegit.rb |    2 +-
    1 files changed, 1 insertions(+), 1 deletions(-)
   ```

_1 more step(s) in references/source-text.md._

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
7. Assuming Jessica is still on her checked-out `featureB` branch, she can now merge Josie’s work into that branch with `git merge`:
   ```bash
   git merge origin/featureBee
   ```
   Expected output (excerpt):
   ```text
   Auto-merging lib/simplegit.rb
   Merge made by the 'recursive' strategy.
    lib/simplegit.rb |    4 ++++
    1 files changed, 4 insertions(+), 0 deletions(-)
   ```
8. Rather, since Josie has already started an upstream `featureBee` branch, Jessica wants to push to that branch, which she does with:
   ```bash
   git push -u origin featureB:featureBee
   ```
9. Run:
   ```text
   ...
   To jessica@githost:simplegit.git
      fba9af8..cd685d1  featureB -> featureBee
   ```
10. Again, Jessica runs a simple `git fetch` to fetch all new content from the server, including (of course) John’s latest work:
   ```bash
   git fetch origin
   ```
   Expected output (excerpt):
   ```text
   ...
   From jessica@githost:simplegit
      3300904..aad881d  featureA   -> origin/featureA
   ```
11. Jessica can display the log of John’s new work by comparing the content of the newly-fetched `featureA` branch with her local copy of the same branch:
   ```bash
   git log featureA..origin/featureA
   ```
   Expected output (excerpt):
   ```text
   commit aad881d154acdaeb2b6b18ea0e827ed8a6d671e6
   Author: John Smith <jsmith@example.com>
   Date:   Fri May 29 19:57:33 2009 -0700
       Increase log output to 30 from 25
   ```
12. If Jessica likes what she sees, she can merge John’s new work into her local `featureA` branch with:
   ```bash
   git checkout featureA
   git merge origin/featureA
   ```
   Expected output (excerpt):
   ```text
   Switched to branch 'featureA'
   Updating 3300904..aad881d
   Fast forward
    lib/simplegit.rb |   10 +++++++++-
   ```

_2 more step(s) in references/source-text.md._

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
7. You start a new branch based off the current `origin/master` branch, squash the `featureB` changes there, resolve any conflicts, make the implementation change, and then push that as a new branch:
   ```bash
   git checkout -b featureBv2 origin/master
   git merge --squash featureB
   git commit
   git push myfork featureBv2
   ```
   Expected output (excerpt):
   ```text
     ... change implementation ...
   ```

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
7. After this is done, you can use `git send-email` to send your patches:
   ```bash
   git send-email *.patch
   ```
   Expected output (excerpt):
   ```text
   0001-add-limit-to-log-function.patch
   0002-increase-log-output-to-30-from-25.patch
   Who should the emails appear to be from? [Jessica Smith <jessica@example.com>]
   ```
8. Run:
   ```text
   Emails will be sent from: Jessica Smith <jessica@example.com>
   Who should the emails be sent to? jessica@example.com
   Message-ID to be used as In-Reply-To for the first email? y
   ```
9. Then, Git spits out a bunch of log information looking something like this for each patch you’re sending:
   ```text
   (mbox) Adding cc: Jessica Smith <jessica@example.com> from
     \line 'From: Jessica Smith <jessica@example.com>'
   OK. Log says:
   Sendmail: /usr/sbin/sendmail -i jessica@example.com
   From: Jessica Smith <jessica@example.com>
   To: jessica@example.com
   Subject: [PATCH 1/2] Add limit to log function
   Date: Sat, 30 May 2009 13:29:15 -0700
   Message-Id: <1243715356-61726-1-git-send-email-jessica@example.com>
   X-Mailer: git-send-email 1.6.2.rc1.20.g8c5b.dirty
   In-Reply-To: <y>
   References: <y>
   Result: OK
   ```

**Verify:** run `cat *.patch |git imap-send` - expect something like:
```text
Resolving imap.gmail.com... ok
Connecting to [74.125.142.109]:993... ok
Logging in...
sending 2 messages
100% (2/2) done
```
