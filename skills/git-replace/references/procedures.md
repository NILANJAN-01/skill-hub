# More procedures: Replace

### Replace

**Goal:** The `replace` command lets you specify an object in Git and say "every time you refer to this object, pretend it’s a different object".

**Steps:**

1. We’ll use a simple repository with five simple commits:
   ```bash
   git log --oneline
   ```
   Expected output (excerpt):
   ```text
   ef989d8 Fifth commit
   c6e1e95 Fourth commit
   9c68fdc Third commit
   945704c Second commit
   ```
2. Well, creating the historical history is easy, we can just put a branch in the history and then push that branch to the `master` branch of a new remote repository.
   ```bash
   git branch history c6e1e95
   git log --oneline --decorate
   ```
   Expected output (excerpt):
   ```text
   ef989d8 (HEAD, master) Fifth commit
   c6e1e95 (history) Fourth commit
   9c68fdc Third commit
   945704c Second commit
   ```
3. Now we can push the new `history` branch to the `master` branch of our new repository:
   ```bash
   git remote add project-history https://github.com/schacon/project-history
   git push project-history history:master
   ```
   Expected output (excerpt):
   ```text
   Counting objects: 12, done.
   Delta compression using up to 2 threads.
   Compressing objects: 100% (4/4), done.
   Writing objects: 100% (12/12), 907 bytes, done.
   ```
4. We need an overlap so we can replace a commit in one with an equivalent commit in the other, so we’re going to truncate this to just commits four and five (so commit four overlaps).
   ```bash
   git log --oneline --decorate
   ```
   Expected output (excerpt):
   ```text
   ef989d8 (HEAD, master) Fifth commit
   c6e1e95 (history) Fourth commit
   9c68fdc Third commit
   945704c Second commit
   ```
5. We can create our base commit using the `commit-tree` command, which just takes a tree and will give us a brand new, parentless commit object SHA-1 back.
   ```bash
   echo 'Get history from blah blah blah' | git commit-tree 9c68fdc^{tree}
   ```
   Expected output (excerpt):
   ```text
   622e88e9cbfbacfb75b5279245b9fb38dfea10cf
   ```
6. The `--onto` argument will be the SHA-1 we just got back from `commit-tree` and the rebase point will be the third commit (the parent of the first commit we want to keep, `9c68fdc`):
   ```bash
   git rebase --onto 622e88 9c68fdc
   ```
   Expected output (excerpt):
   ```text
   First, rewinding head to replay your work on top of it...
   Applying: fourth commit
   Applying: fifth commit
   ```
7. To get the history data after cloning this truncated repository, one would have to add a second remote for the historical repository and fetch:
   ```bash
   git clone https://github.com/schacon/project
   cd project
   git log --oneline master
   git remote add project-history https://github.com/schacon/project-history
   git fetch project-history
   ```
   Expected output (excerpt):
   ```text
   e146b5f Fifth commit
   81a708d Fourth commit
   622e88e Get history from blah blah blah
   From https://github.com/schacon/project-history
   ```
8. Run:
   ```text
    * [new branch]      master     -> project-history/master
   ```
9. Now the collaborator would have their recent commits in the `master` branch and the historical commits in the `project-history/master` branch.
   ```bash
   git log --oneline master
   git log --oneline project-history/master
   ```
   Expected output (excerpt):
   ```text
   e146b5f Fifth commit
   81a708d Fourth commit
   622e88e Get history from blah blah blah
   c6e1e95 Fourth commit
   ```
10. So we want to replace the "fourth" commit in the `master` branch with the "fourth" commit in the `project-history/master` branch:
   ```bash
   git replace 81a708d c6e1e95
   ```
11. Now, if you look at the history of the `master` branch, it appears to look like this:
   ```bash
   git log --oneline master
   ```
   Expected output (excerpt):
   ```text
   e146b5f Fifth commit
   81a708d Fourth commit
   9c68fdc Third commit
   945704c Second commit
   ```
12. Even if you run a command like `cat-file`, it will show you the replaced data:
   ```bash
   git cat-file -p 81a708d
   ```
   Expected output (excerpt):
   ```text
   tree 7bc544cf438903b65ca9104a1e30345eee6c083d
   parent 9c68fdceee073230f19ebb8b5e7fc71b479c0252
   author Scott Chacon <schacon@gmail.com> 1268712581 -0700
   committer Scott Chacon <schacon@gmail.com> 1268712581 -0700
   ```

_2 more step(s) in references/source-text.md._

**Verify:** run `git cat-file -p 81a708d` - expect something like:
```text
tree 7bc544cf438903b65ca9104a1e30345eee6c083d
parent 9c68fdceee073230f19ebb8b5e7fc71b479c0252
author Scott Chacon <schacon@gmail.com> 1268712581 -0700
committer Scott Chacon <schacon@gmail.com> 1268712581 -0700
fourth commit
```
