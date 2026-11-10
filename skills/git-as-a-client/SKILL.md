---
name: git-as-a-client
description: "Git as a Client playbook extracted from \"Pro Git\". This tool allows you to use Git as a valid client to a Subversion server, so you can use all the local features of Git and then push to a Subversion server as if you were using Subversion locally. Use when the user asks about git as a client, git svn, perforce git fusion, subversion server, git commit, perforce server, git repository; or mentions git svn, git log --oneline --all, git p4, git log --oneline --graph, git push, git clone; or hits errors like \"ERROR from SVN:\"."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git as a Client"
  category: git-integrations
  source: "Pro Git, 2nd edition"
  pages: "373-405"
---

# Git as a Client

This tool allows you to use Git as a valid client to a Subversion server, so you can use all the local features of Git and then push to a Subversion server as if you were using Subversion locally.

_Built from "Pro Git" (pages 373-405) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **git as a client** (git svn, perforce git fusion, subversion server, git commit, perforce server).
- The user wants to run or understand `git svn`.
- The user wants to run or understand `git log --oneline --all`.
- The user wants to run or understand `git p4`.
- The user wants to run or understand `git log --oneline --graph`.
- The user sees an error like `ERROR from SVN:`.
- This tool allows you to use Git as a valid client to a Subversion server, so you can use all the local features of Git and then push to a Subversion server as if you were using Subversion locally.
- The second is git-p4, a client-side bridge that lets you use Git as a Perforce client, without requiring any reconfiguration of the Perforce server.
- If you want to freely mix the use of Perforce and Git as clients for source control, and you can convince the server administrator to install it, Git Fusion makes using Git a first-class version-control client for a Perforce server.

## When NOT to use

- For migrating to git, use the `git-migrating-to-git` skill instead.
- For contributing to a project, use the `git-distributed-git-contributing-to-a-project` skill instead.
- For advanced merging, use the `git-advanced-merging` skill instead.

## Key concepts

- However, you can create and commit to branches in Subversion using `git svn`.
- The good news, if you prefer Git’s client-side behavior but are working with a project whose source code is controlled with Mercurial, is that there’s a way to use Git as a client for a Mercurial-hosted repository.
- Since Git and Mercurial are both designed for every client to have a full copy of the repository history, this command makes a full clone, including all the project’s history, and does it fairly quickly.
- The second is git-p4, a client-side bridge that lets you use Git as a Perforce client, without requiring any reconfiguration of the Perforce server.
- This is actually fairly easy to do using your favorite Perforce client; just map the `//.git-fusion` directory on the Perforce server into your workspace.
- This is a mapping between a Perforce branch and a Git branch.
- If you want to freely mix the use of Perforce and Git as clients for source control, and you can convince the server administrator to install it, Git Fusion makes using Git a first-class version-control client for a Perforce server.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git svn rebase`
  - `git p4 rebase`
- Don’t rewrite your history and try to push again, and don’t push to a parallel Git repository to collaborate with fellow Git developers at the same time.
- The branch name “permanent” was recorded with the changeset marked 7.
- One thing you should know is that Mercurial doesn’t support rewriting history, only adding to it.
- Changesets 8, 9, and 10 have been created and belong to the `permanent` branch, but the old changesets are still there.
- That’s not to say that Perforce will be happy with everything you throw at it – if you try to rewrite history that’s already been pushed, Git Fusion will reject it – but Git Fusion tries very hard to feel native.
- If you merge two branches in Git and try to submit the new changeset, all that will be recorded is a bunch of file changes; the metadata about which branches are involved in the integration will be lost.

## Procedures

### Git and Subversion

**Goal:** This tool allows you to use Git as a valid client to a Subversion server, so you can use all the local features of Git and then push to a Subversion server as if you were using Subversion locally.

**Steps:**

1. To follow along, you first need to create a new local Subversion repository:
   ```bash
   mkdir /tmp/test-svn
   svnadmin create /tmp/test-svn
   ```
2. Then, enable all users to change revprops – the easy way is to add a `pre-revprop-change` script that always exits 0:
   ```bash
   cat /tmp/test-svn/hooks/pre-revprop-change
   chmod +x /tmp/test-svn/hooks/pre-revprop-change
   ```
   Expected output (excerpt):
   ```text
   #!/bin/sh
   exit 0;
   ```
3. You can now sync this project to your local machine by calling `svnsync init` with the to and from repositories.
   ```bash
   svnsync init file:///tmp/test-svn \
   http://your-svn-server.example.org/svn/
   ```
4. You can then clone the code by running:
   ```bash
   svnsync sync file:///tmp/test-svn
   ```
   Expected output (excerpt):
   ```text
   Committed revision 1.
   Copied properties for revision 1.
   Transmitting file data .............................[...]
   Committed revision 2.
   ```
5. Subversion repository:
   ```bash
   git svn clone file:///tmp/test-svn -T trunk -b branches -t tags
   ```
   Expected output (excerpt):
   ```text
   Initialized empty Git repository in /private/tmp/progit/test-svn/.git/
   r1 = dcbfb5891860124cc2e8cc616cded42624897125 (refs/remotes/origin/trunk)
       A   m4/acx_pthread.m4
       A   m4/stl_hash.m4
   ```
6. The following command is equivalent:
   ```bash
   git svn clone file:///tmp/test-svn -s
   ```

_20 more step(s) in references/procedures.md._

**Verify:** run `git log -1` - expect something like:
```text
commit 95e0222ba6399739834380eb10afcd73e0670bc5
Author: ben <ben@0b684db3-b064-4277-89d1-21af03df0a68>
Date:   Thu Jul 24 03:08:36 2014 +0000
    Adding git-svn instructions to the README
    git-svn-id: file:///tmp/test-svn/trunk@77 0b684db3-b064-4277-89d1-21af03df0a68
```

**If it fails:** To resolve this situation, you can run `git svn rebase`, which pulls down any changes on the server that you don’t have yet and rebases any work you have on top of what is on the server:

### Git and Mercurial

**Goal:** The last thing you’ll need is the Mercurial client.

**Steps:**

1. This basically entails dropping its file somewhere in your path, like so:
   ```bash
   curl -o ~/bin/git-remote-hg \
   https://raw.githubusercontent.com/felipec/git-remote-hg/master/git-remote-hg
   chmod +x ~/bin/git-remote-hg
   ```
2. If you have Python installed, this is as simple as:
   ```bash
   pip install mercurial
   ```
3. Mercurial repository can act this way, so we’ll just use the "hello world" repository everyone uses to learn Mercurial:
   ```bash
   hg clone http://selenic.com/repo/hello /tmp/hello
   ```
4. As always with Git, first we clone:
   ```bash
   git clone hg::/tmp/hello /tmp/hello-git
   cd /tmp/hello-git
   git log --oneline --graph --decorate
   ```
   Expected output (excerpt):
   ```text
   * ac7955c (HEAD, origin/master, origin/branches/default, origin/HEAD,
   refs/hg/origin/branches/default, refs/hg/origin/bookmarks/master, master) Create a
   makefile
   * 65bb417 Create a standard 'hello, world' program
   ```
5. Let’s take a look at what’s actually in the `.git` directory:
   ```bash
   tree .git/refs
   ```
   Expected output (excerpt):
   ```text
   .git/refs
   ├── heads
   │   └── master
   ├── hg
   ```
6. Run:
   ```text
   │       └── HEAD
   └── tags
   9 directories, 5 files
   ```

_14 more step(s) in references/procedures.md._

**Verify:** run `hg log --style compact -G` - expect something like:
```text
o  10[tip]   99611176cbc9   2014-08-14 20:21 -0700   ben
|    A permanent change
|
o  9   f23e12f939c3   2014-08-14 20:01 -0700   ben
|    Add some documentation
|
```

### Git and Perforce

**Goal:** The second is git-p4, a client-side bridge that lets you use Git as a Perforce client, without requiring any reconfiguration of the Perforce server.

**Steps:**

1. Then use these commands to create a user:
   ```bash
   p4 -p localhost:1666 -u super user -f john
   p4 -p localhost:1666 -u john passwd
   exit
   ```
2. If this is going to be a permanent installation, consult the Perforce Git Fusion manual to install a different certificate; for our example purposes, this will suffice:
   ```bash
   export GIT_SSL_NO_VERIFY=true
   ```
3. Now we can test that everything is working.
   ```bash
   git clone https://10.0.1.254/Talkhouse
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'Talkhouse'...
   Username for 'https://10.0.1.254': john
   Password for 'https://john@10.0.1.254':
   remote: Counting objects: 630, done.
   ```
4. The file structure looks like this:
   ```bash
   tree
   ```
   Expected output (excerpt):
   ```text
   .
   ├── objects
   │   ├── repos
   │   │   └── [...]
   ```
5. Let’s take a look at the file in the root:
   ```ini
   [repo-creation]
   charset = utf8
   [git-to-perforce]
   change-owner = author
   enable-git-branch-creation = yes
   enable-swarm-reviews = yes
   enable-git-merge-commits = yes
   enable-git-submodules = yes
   preflight-commit = none
   ignore-author-permissions = no
   read-permission-check = none
   git-merge-avoidance-after-change-num = 12107
   [perforce-to-git]
   http-url = none
   ssh-url = none
   # ... (full listing in references)
   ```
6. You’ll also see sections that look like this:
   ```ini
   [Talkhouse-master]
   git-branch-name = master
   view = //depot/Talkhouse/main-dev/... ...
   ```

_28 more step(s) in references/procedures.md._

**Verify:** run `git log --oneline --all --graph --decorate` - expect something like:
```text
* 3be6fd8 (HEAD, master) Correct email address
*   1dcbf21 Merge remote-tracking branch 'p4/master'
```

More procedures in [references/procedures.md](references/procedures.md):

- Git and Subversion
- Git and Mercurial
- Git and Perforce

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git svn` | One of Git’s great features is a bidirectional bridge to Subversion called `git svn`. | `git svn log` |
| `git log --oneline --all` | Once it’s finished, we have a fully-functional Git repository | `git log --oneline --all --graph --decorate` |
| `git p4` | You can probably tell from the output, but `git p4 rebase` is a shortcut for `git p4 sync` followed by `git rebase p4/master`. | `git p4 sync` |
| `git log --oneline --graph` | As always with Git, first we clone | `git log --oneline --graph --decorate` |
| `git push` | The result is as though we just did a `git push`, which is the closest analogy to what actually did happen. | `git push` |
| `git clone` | You’ll notice that working with a Mercurial repository uses the standard `git clone` command. | `git clone https://10.0.1.254/Jam` |
| `export` | If this is going to be a permanent installation, consult the Perforce Git Fusion manual to install a different certificate; for our example purposes, this will suffice | `export P4USER=john` |
| `git log --oneline --decorate` | We’ll assume we’ve mapped in the “Jam” project using a configuration file as shown above, which we can clone like this | `git log --oneline --decorate --graph --all` |
| `chmod` | Then, enable all users to change revprops – the easy way is to add a `pre-revprop-change` script that always exits 0 | `chmod +x ~/bin/git-remote-hg` |
| `git branch -a` | At this point, you should have a valid Git repository that has imported your branches and tags | `git branch -a` |
| `git show-ref` | Let’s take a closer look with the Git plumbing command `show-ref` | `git show-ref` |
| `git commit -am` | If you edit one of the files and commit it, you have a commit that exists in Git locally that doesn’t exist on the Subversion server | `git commit -am 'A permanent change'` |
| `git log` | Git-p4 has created some refs to represent the state of the server, and they look like remote refs to `git log`, but they’re not managed by Git itself, and you can’t push to them. | `git log -1` |
| `git cat-file -p` | Let’s explore a bit | `git cat-file -p ac9117f` |
| `git fetch` | Git fetches the tags directly into `refs/tags`, rather than treating them as remote branches. | `git fetch` |
| `git merge` | Now, if you want to merge your `opera` branch into `trunk` (your `master` branch), you can do so with a normal `git merge`. | `git merge origin/master` |
| `git checkout -b` | If we now `git checkout -b dev p4/project/dev` and make some commits, git-p4 is smart enough to target the right branch when we do `git p4 submit`. | `git checkout -b featureA` |
| `hg log --style -G` | On the Mercurial side, it looks like this | `hg log --style compact -G` |
| `p4 -p -u` | Then use these commands to create a user | `p4 -p localhost:1666 -u john passwd` |
| `svnadmin create` | To follow along, you first need to create a new local Subversion repository | `svnadmin create /tmp/test-svn` |

## Decision guide

- If you’re working with a team, and some are using SVN and others are using Git, make sure everyone is using the SVN server to collaborate – doing so will make your life easier.
- Although this operation may take only a few minutes, if you try to copy the original repository to another remote repository instead of a local one, the process will take nearly an hour, even though there are fewer than 100 commits.
- If you’re pushing to a Subversion server via `git svn`, you may want to rebase your work onto a single branch each time instead of merging branches together.
- The reason to prefer rebasing is that Subversion has a linear history and doesn’t deal with merges like
- But you need to provide a descriptive commit message (via `-m`), or the merge will say “Merge branch opera” instead of something useful.
- The good news, if you prefer Git’s client-side behavior but are working with a project whose source code is controlled with Mercurial, is that there’s a way to use Git as a client for a Mercurial-hosted repository.
- If you avoid changing history that’s left your machine (as is generally recommended), you may not even be aware that the other end is Mercurial.
- If you’ve never seen this view before, it may seem confusing, but it shows the same concepts as a graphical viewer for Git history.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `ERROR from SVN:` | To resolve this situation, you can run `git svn rebase`, which pulls down any changes on the server that you don’t have yet and rebases any work you have on top of what is on the server: |

- **Note:** You’ll need the `p4` tool somewhere in your `PATH` to work with git-p4. As of this writing, it is freely available at https://www.perforce.com/downloads/helix-command-line-client-p4.

## Related skills

- `git-migrating-to-git` - Migrating to Git
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-advanced-merging` - Advanced Merging
- `git-branches-in-a-nutshell` - Branches in a Nutshell

## Source

"Pro Git", pages 373-405. Sections: Git as a Client; Git as a Client > Git and Subversion; Git as a Client > Git and Mercurial; Git as a Client > Git and Perforce.
