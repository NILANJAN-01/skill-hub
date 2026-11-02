# More procedures: Branch Management

### Changing a branch name

**Goal:** You also want to change the branch name on the remote (GitHub, GitLab, other server).

**Steps:**

1. Rename the branch locally with the `git branch --move` command:
   ```bash
   git branch --move bad-branch-name corrected-branch-name
   ```
2. To let others see the corrected branch on the remote, push it:
   ```bash
   git push --set-upstream origin corrected-branch-name
   ```
3. Now we’ll take a brief look at where we are now:
   ```bash
   git branch --all
   ```
   Expected output (excerpt):
   ```text
   * corrected-branch-name
     main
     remotes/origin/bad-branch-name
     remotes/origin/corrected-branch-name
   ```
4. However, the branch with the bad name is also still present there but you can delete it by executing the following command:
   ```bash
   git push origin --delete bad-branch-name
   ```
5. Rename your local `master` branch into `main` with the following command:
   ```bash
   git branch --move master main
   ```
6. This makes the renamed branch available on the remote.
   ```bash
   git push --set-upstream origin main
   ```
7. Now we end up with the following state:
   ```bash
   git branch --all
   ```
   Expected output (excerpt):
   ```text
   * main
     remotes/origin/HEAD -> origin/master
     remotes/origin/main
     remotes/origin/master
   ```
8. After you’ve done all these tasks, and are certain the `main` branch performs just as the `master` branch, you can delete the `master` branch:
   ```bash
   git push origin --delete master
   ```
