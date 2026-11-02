# More procedures: Maintenance and Data Recovery

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
7. Run:
   ```text
   cac0cab538b970a37ea1e769cbbde608743bc96d Second commit
   fdf4fc3344e67ab068f836878b6c4951e3b15f3d First commit
   ```
8. Now the first two commits aren’t reachable by anything:
   ```bash
   git branch -D recover-branch
   rm -Rf .git/logs/
   ```
9. If you run it with the `--full` option, it shows you all objects that aren’t pointed to by another object:
   ```bash
   git fsck --full
   ```
   Expected output (excerpt):
   ```text
   Checking object directories: 100% (256/256), done.
   Checking objects: 100% (18/18), done.
   dangling blob d670460b4b4aece5915caf5c68d12f560a9fe3e4
   dangling commit ab1afef80fac8e34258ff41fc1b867c702daa24b
   ```

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
7. You can easily see what commits modified this file:
   ```bash
   git log --oneline --branches -- git.tgz
   ```
   Expected output (excerpt):
   ```text
   dadf725 Oops - remove large tarball
   7b30847 Add git tarball
   ```
8. To do so, you use `filter-branch`, which you used in Rewriting History:
   ```bash
   git filter-branch --index-filter \
   'git rm --ignore-unmatch --cached git.tgz' -- 7b30847^..
   ```
   Expected output (excerpt):
   ```text
   Rewrite 7b30847d080183a1ab7d18fb202473b3096e9f34 (1/2)rm 'git.tgz'
   Rewrite dadf7258d699da2c8d89b09ef6670edb7d5f91b4 (2/2)
   Ref 'refs/heads/master' was rewritten
   ```
9. You need to get rid of anything that has a pointer to those old commits before you repack:
   ```bash
   rm -Rf .git/refs/original
   rm -Rf .git/logs/
   git gc
   ```
   Expected output (excerpt):
   ```text
   Counting objects: 15, done.
   Delta compression using up to 8 threads.
   Compressing objects: 100% (11/11), done.
   Writing objects: 100% (15/15), done.
   ```
10. Let’s see how much space you saved.
   ```bash
   git count-objects -v
   ```
   Expected output (excerpt):
   ```text
   count: 11
   size: 4904
   in-pack: 15
   packs: 1
   ```
11. If you really wanted to, you could remove the object completely by running `git prune` with the `--expire` option:
   ```bash
   git prune --expire now
   git count-objects -v
   ```
   Expected output (excerpt):
   ```text
   count: 0
   size: 0
   in-pack: 15
   packs: 1
   ```

**Verify:** run `git log --oneline --branches -- git.tgz` - expect something like:
```text
dadf725 Oops - remove large tarball
7b30847 Add git tarball
```
