# More procedures: Tagging

### Deleting Tags

**Goal:** Deleting Tags

**Steps:**

1. For example, we could remove our lightweight tag above as follows:
   ```bash
   git tag -d v1.4-lw
   ```
   Expected output (excerpt):
   ```text
   Deleted tag 'v1.4-lw' (was e7d5add)
   ```
2. The first variation is `git push <remote> :refs/tags/<tagname>`:
   ```bash
   git push origin :refs/tags/v1.4-lw
   ```
   Expected output (excerpt):
   ```text
   To /git@github.com:schacon/simplegit.git
    - [deleted]         v1.4-lw
   ```
3. The second (and more intuitive) way to delete a remote tag is with:
   ```bash
   git push origin --delete <tagname>
   ```

### Checking out Tags

**Goal:** Checking out Tags

**Steps:**

1. If you want to view the versions of files a tag is pointing to, you can do a `git checkout` of that tag, although this puts your repository in “detached HEAD” state, which has some ill side effects:
   ```bash
   git checkout v2.0.0
   git checkout v2.0-beta-0.1
   ```
   Expected output (excerpt):
   ```text
   Note: switching to 'v2.0.0'.
   You are in 'detached HEAD' state. You can look around, make experimental
   changes and commit them, and you can discard any commits you make in this
   state without impacting any branches by performing another checkout.
   ```
2. Thus, if you need to make changes — say you’re fixing a bug on an older version, for instance — you will generally want to create a branch:
   ```bash
   git checkout -b version2 v2.0.0
   ```
   Expected output (excerpt):
   ```text
   Switched to a new branch 'version2'
   ```

**If it fails:** Thus, if you need to make changes — say you’re fixing a bug on an older version, for instance — you will generally want to create a branch:
