---
name: git-maintenance-and-data-recovery
description: "Maintenance and Data Recovery playbook extracted from \"Pro Git\". Because the reflog data is kept in the .git/logs/ directory, you effectively have no reflog. Use when the user asks about maintenance and data recovery, git reflog, loose objects, git history; or mentions git log --pretty, rm -Rf, git count-objects -v, git commit -m, git gc, git gc --auto."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Maintenance and Data Recovery"
  category: git-internals
  source: "Pro Git, 2nd edition"
  pages: "446-453"
---

# Maintenance and Data Recovery

Because the reflog data is kept in the `.git/logs/` directory, you effectively have no reflog.

_Built from "Pro Git" (pages 446-453) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **maintenance and data recovery** (git reflog, loose objects, git history).
- The user wants to run or understand `git log --pretty`.
- The user wants to run or understand `rm -Rf`.
- The user wants to run or understand `git count-objects -v`.
- The user wants to run or understand `git commit -m`.

## When NOT to use

- For git references, use the `git-references` skill instead.
- For packfiles, use the `git-packfiles` skill instead.
- For migrating to git, use the `git-migrating-to-git` skill instead.

## Key concepts

- If you run `git gc`, you’ll no longer have these files in the `refs` directory.
- You need to find the latest commit SHA-1 and then add a branch that points to it.
- It looks like the bottom commit is the one you lost, so you can recover it by creating a new branch at that commit.
- However, if someone at any point in the history of your project added a single huge file, every clone for all time will be forced to download that large file, even if it was removed from the project in the very next commit.
- It rewrites every commit object since the earliest tree you have to modify to remove a large file reference.
- If you run `git gc`, all the objects are in a packfile; you can identify the big objects by running another plumbing command called `gitverify-pack` and sorting on the third field in the output, which is file size.
- You must rewrite all the commits downstream from `7b30847` to fully remove this file from your Git history.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git reset --hard 1a410efbd13591db07496601ebc7a059dd55cfe9`
  - `git branch -D recover-branch`
  - `git filter-branch --index-filter \`
  - `git prune --expire now`
- Occasionally, you may have to do some cleanup – make a repository more compact, clean up an imported repository, or recover lost work.
- At some point in your Git journey, you may accidentally lose a commit.
- Generally, this happens because you force-delete a branch that had work on it, and it turns out you wanted the branch after all; or you hard-reset a branch, thus abandoning commits that you wanted something from.
- You’ve effectively lost the top two commits – you have no branch from which those commits are reachable.
- It looks like the bottom commit is the one you lost, so you can recover it by creating a new branch at that commit.
- However, if someone at any point in the history of your project added a single huge file, every clone for all time will be forced to download that large file, even if it was removed from the project in the very next commit.

## Procedures

### Maintenance

**Goal:** Maintenance

**Steps:**

1. You can run `auto gc` manually as follows:
   ```bash
   git gc --auto
   ```
2. Suppose your repository contains the following branches and tags:
   ```bash
   find .git/refs -type f
   ```
3. Run:
   ```text
   .git/refs/heads/experiment
   .git/refs/heads/master
   .git/refs/tags/v1.0
   .git/refs/tags/v1.1
   ```
4. Git will move them for the sake of efficiency into a file named `.git/packed-refs` that looks like this:
   ```bash
   cat .git/packed-refs
   ```
   Expected output (excerpt):
   ```text
   # pack-refs with: peeled fully-peeled
   cac0cab538b970a37ea1e769cbbde608743bc96d refs/heads/experiment
   ab1afef80fac8e34258ff41fc1b867c702daa24b refs/heads/master
   cac0cab538b970a37ea1e769cbbde608743bc96d refs/tags/v1.0
   ```

**Verify:** run `cat .git/packed-refs` - expect something like:
```text
# pack-refs with: peeled fully-peeled
cac0cab538b970a37ea1e769cbbde608743bc96d refs/heads/experiment
ab1afef80fac8e34258ff41fc1b867c702daa24b refs/heads/master
cac0cab538b970a37ea1e769cbbde608743bc96d refs/tags/v1.0
9585191f37f7b0fb9444f35a9bf50de191beadc2 refs/tags/v1.1
^1a410efbd13591db07496601ebc7a059dd55cfe9
```

### Data Recovery

**Goal:** Because the reflog data is kept in the `.git/logs/` directory, you effectively have no reflog.

**Steps:**

1. First, let’s review where your repository is at this point:
   ```bash
   git log --pretty=oneline
   ```
   Expected output (excerpt):
   ```text
   ab1afef80fac8e34258ff41fc1b867c702daa24b Modify repo.rb a bit
   484a59275031909e19aadb7c92262719cfcdf19a Create repo.rb
   1a410efbd13591db07496601ebc7a059dd55cfe9 Third commit
   cac0cab538b970a37ea1e769cbbde608743bc96d Second commit
   ```
2. Now, move the `master` branch back to the middle commit:
   ```bash
   git reset --hard 1a410efbd13591db07496601ebc7a059dd55cfe9
   git log --pretty=oneline
   ```
   Expected output (excerpt):
   ```text
   HEAD is now at 1a410ef Third commit
   1a410efbd13591db07496601ebc7a059dd55cfe9 Third commit
   ```
3. Run:
   ```text
   cac0cab538b970a37ea1e769cbbde608743bc96d Second commit
   fdf4fc3344e67ab068f836878b6c4951e3b15f3d First commit
   ```
4. You can see where you’ve been at any time by running `git reflog`:
   ```bash
   git reflog
   ```
   Expected output (excerpt):
   ```text
   1a410ef HEAD@{0}: reset: moving to 1a410ef
   ab1afef HEAD@{1}: commit: Modify repo.rb a bit
   484a592 HEAD@{2}: commit: Create repo.rb
   ```
5. To see the same information in a much more useful way, we can run `git log -g`, which will give you a normal log output for your reflog.
   ```bash
   git log -g
   ```
   Expected output (excerpt):
   ```text
   commit 1a410efbd13591db07496601ebc7a059dd55cfe9
   Reflog: HEAD@{0} (Scott Chacon <schacon@gmail.com>)
   Reflog message: updating HEAD
   Author: Scott Chacon <schacon@gmail.com>
   ```
6. For example, you can start a branch named `recover-branch` at that commit (ab1afef):
   ```bash
   git branch recover-branch ab1afef
   git log --pretty=oneline recover-branch
   ```
   Expected output (excerpt):
   ```text
   ab1afef80fac8e34258ff41fc1b867c702daa24b Modify repo.rb a bit
   484a59275031909e19aadb7c92262719cfcdf19a Create repo.rb
   1a410efbd13591db07496601ebc7a059dd55cfe9 Third commit
   ```

_3 more step(s) in references/procedures.md._

**Verify:** run `git log -g` - expect something like:
```text
commit 1a410efbd13591db07496601ebc7a059dd55cfe9
Reflog: HEAD@{0} (Scott Chacon <schacon@gmail.com>)
Reflog message: updating HEAD
Author: Scott Chacon <schacon@gmail.com>
Date:   Fri May 22 18:22:37 2009 -0700
        Third commit
```

**If it fails:** Here’s an example that hard-resets the `master` branch in your test repository to an older commit and then recovers the lost commits.

### Removing Objects

**Goal:** This is fine if the whole thing is source code, because Git is highly optimized to compress that data efficiently.

**Steps:**

1. First, add a large object to your history:
   ```bash
   curl -L https://www.kernel.org/pub/software/scm/git/git-2.1.0.tar.gz > git.tgz
   git add git.tgz
   git commit -m 'Add git tarball'
   ```
   Expected output (excerpt):
   ```text
   [master 7b30847] Add git tarball
    1 file changed, 0 insertions(+), 0 deletions(-)
    create mode 100644 git.tgz
   ```
2. Better get rid of it:
   ```bash
   git rm git.tgz
   git commit -m 'Oops - remove large tarball'
   ```
   Expected output (excerpt):
   ```text
   rm 'git.tgz'
   [master dadf725] Oops - remove large tarball
    1 file changed, 0 insertions(+), 0 deletions(-)
    delete mode 100644 git.tgz
   ```
3. Now, `gc` your database and see how much space you’re using:
   ```bash
   git gc
   ```
   Expected output (excerpt):
   ```text
   Counting objects: 17, done.
   Delta compression using up to 8 threads.
   Compressing objects: 100% (13/13), done.
   Writing objects: 100% (17/17), done.
   ```
4. You can run the `count-objects` command to quickly see how much space you’re using:
   ```bash
   git count-objects -v
   ```
   Expected output (excerpt):
   ```text
   count: 7
   size: 32
   in-pack: 17
   packs: 1
   ```
5. You can also pipe it through the `tail` command because you’re only interested in the last few largest files:
   ```bash
   git verify-pack -v .git/objects/pack/pack-29…69.idx \
   | sort -k 3 -n \
   | tail -3
   ```
   Expected output (excerpt):
   ```text
   dadf7258d699da2c8d89b09ef6670edb7d5f91b4 commit 229 159 12
   033b4468fa6b2a9547a70d88d1bbe8bf3f9ed0d5 blob   22044 5792 4977696
   82c99a3e86bb1267b236a4b6eff7868d97489af1 blob   4975916 4976258 1438
   ```
6. You can use this to find your blob’s name:
   ```bash
   git rev-list --objects --all | grep 82c99a3
   ```
   Expected output (excerpt):
   ```text
   82c99a3e86bb1267b236a4b6eff7868d97489af1 git.tgz
   ```

_5 more step(s) in references/procedures.md._

**Verify:** run `git log --oneline --branches -- git.tgz` - expect something like:
```text
dadf725 Oops - remove large tarball
7b30847 Add git tarball
```

More procedures in [references/procedures.md](references/procedures.md):

- Data Recovery
- Removing Objects

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git log --pretty` | First, let’s review where your repository is at this point | `git log --pretty=oneline` |
| `git count-objects -v` | You can run the `count-objects` command to quickly see how much space you’re using | `git count-objects -v` |
| `git commit -m` | First, add a large object to your history | `git commit -m 'Add git tarball'` |
| `git gc` | If you run `git gc`, you’ll no longer have these files in the `refs` directory. | `git gc` |
| `git gc --auto` | You can run `auto gc` manually as follows | `git gc --auto` |
| `git reset --hard` | Now, move the `master` branch back to the middle commit | `git reset --hard 1a410efbd13591db07496601ebc7a059dd55cfe9` |
| `git reflog` | Often, the quickest way is to use a tool called `git reflog`. | `git reflog` |
| `git log -g` | To see the same information in a much more useful way, we can run `git log -g`, which will give you a normal log output for your reflog. | `git log -g` |
| `git branch` | For example, you can start a branch named `recover-branch` at that commit (ab1afef) | `git branch recover-branch ab1afef` |
| `git branch -D` | Now the first two commits aren’t reachable by anything | `git branch -D recover-branch` |
| `git fsck --full` | If you run it with the `--full` option, it shows you all objects that aren’t pointed to by another object | `git fsck --full` |
| `curl -L` | First, add a large object to your history | `curl -L https://www.kernel.org/pub/software/scm/git/git-2.1.0.tar.gz > git.tgz` |
| `git add` | However, your reflog and a new set of refs that Git added when you did the `filter-branch` under `.git/refs/original` still do, so you have to remove them and then repack the database. | `git add git.tgz` |
| `git rm` | The `--ignore-unmatch` option to `git rm` tells it not to error out if the pattern you’re trying to remove isn’t there. | `git rm git.tgz` |
| `git verify-pack -v -k` | You can also pipe it through the `tail` command because you’re only interested in the last few largest files | `git verify-pack -v .git/objects/pack/pack-29…69.idx \` |
| `git rev-list --objects --all` | You can use this to find your blob’s name | `git rev-list --objects --all \| grep 82c99a3` |
| `git log --oneline --branches` | You can easily see what commits modified this file | `git log --oneline --branches -- git.tgz` |
| `git filter-branch --index-filter --ignore-unmatch` | To do so, you use `filter-branch`, which you used in Rewriting History | `git filter-branch --index-filter \` |
| `git prune --expire` | If you really wanted to, you could remove the object completely by running `git prune` with the `--expire` option | `git prune --expire now` |

## Decision guide

- If you update a reference, Git doesn’t edit this file but instead writes a new file to `refs/heads`.
- If you did an import from another system or otherwise find that your repository is much larger than it should be, here is how you can find and remove large objects.
- If you do this immediately after an import, before anyone has started to base work on the commit, you’re fine – otherwise, you have to notify all contributors that they must rebase their work onto your new commits.
- The `--index-filter` option is similar to the `--tree-filter` option used in Rewriting History, except that instead of passing a command that modifies files checked out on disk, you’re modifying your staging area or index each time.

## Related skills

- `git-references` - Git References
- `git-packfiles` - Packfiles
- `git-migrating-to-git` - Migrating to Git
- `git-objects` - Git Objects

## Source

"Pro Git", pages 446-453. Sections: Maintenance and Data Recovery; Maintenance and Data Recovery > Maintenance; Maintenance and Data Recovery > Data Recovery; Maintenance and Data Recovery > Removing Objects.
