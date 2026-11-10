# More procedures: Bundling

### Bundling

**Goal:** If you want to send that repository to someone and you don’t have access to a repository to push to, or simply don’t want to set one up, you can bundle it with `git bundle create`.

**Steps:**

1. Let’s say you have a repository with two commits:
   ```bash
   git log
   ```
   Expected output (excerpt):
   ```text
   commit 9a466c572fe88b195efd356c3f2bbeccdb504102
   Author: Scott Chacon <schacon@gmail.com>
   Date:   Wed Mar 10 07:34:10 2010 -0800
       Second commit
   ```
2. If you want to send that repository to someone and you don’t have access to a repository to push to, or simply don’t want to set one up, you can bundle it with `git bundle create`.
   ```bash
   git bundle create repo.bundle HEAD master
   ```
   Expected output (excerpt):
   ```text
   Counting objects: 6, done.
   Delta compression using up to 2 threads.
   Compressing objects: 100% (2/2), done.
   Writing objects: 100% (6/6), 441 bytes, done.
   ```
3. You can clone from the binary file into a directory, much like you would from a URL.
   ```bash
   git clone repo.bundle repo
   cd repo
   git log --oneline
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'repo'...
   ...
   ```
4. Run:
   ```text
   9a466c5 Second commit
   b1ec324 First commit
   ```
5. USB stick or email.
   ```bash
   git log --oneline
   ```
   Expected output (excerpt):
   ```text
   71b84da Last commit - second repo
   c99cf5b Fourth commit - second repo
   7011d3d Third commit - second repo
   9a466c5 Second commit
   ```
6. You can test that with the `log` command.
   ```bash
   git log --oneline master ^origin/master
   ```
   Expected output (excerpt):
   ```text
   71b84da Last commit - second repo
   c99cf5b Fourth commit - second repo
   7011d3d Third commit - second repo
   ```
7. We do that with the `git bundle create` command, giving it a filename we want our bundle to be and the range of commits we want to go into it.
   ```bash
   git bundle create commits.bundle master ^9a466c5
   ```
   Expected output (excerpt):
   ```text
   Counting objects: 11, done.
   Delta compression using up to 2 threads.
   Compressing objects: 100% (3/3), done.
   Writing objects: 100% (9/9), 775 bytes, done.
   ```
8. The first command is the `bundle verify` command that will make sure the file is actually a valid Git bundle and that you have all the necessary ancestors to reconstitute it properly.
   ```bash
   git bundle verify ../commits.bundle
   ```
   Expected output (excerpt):
   ```text
   The bundle contains 1 ref
   71b84daaf49abed142a373b6e5c59a22dc6560dc refs/heads/master
   The bundle requires these 1 ref
   9a466c572fe88b195efd356c3f2bbeccdb504102 second commit
   ```
9. The `verify` command would have looked like this instead:
   ```bash
   git bundle verify ../commits-bad.bundle
   ```
   Expected output (excerpt):
   ```text
   error: Repository lacks these prerequisite commits:
   error: 7011d3d8fc200abe0ad561c011c3852a4b7bbe95 Third commit - second repo
   ```
10. If you want to see what branches are in the bundle that can be imported, there is also a command to just list the heads:
   ```bash
   git bundle list-heads ../commits.bundle
   ```
   Expected output (excerpt):
   ```text
   71b84daaf49abed142a373b6e5c59a22dc6560dc refs/heads/master
   ```
11. Here we’ll fetch the `master` branch of the bundle to a branch named `other-master` in our repository:
   ```bash
   git fetch ../commits.bundle master:other-master
   ```
   Expected output (excerpt):
   ```text
   From ../commits.bundle
    * [new branch]      master     -> other-master
   ```
12. Now we can see that we have the imported commits on the `other-master` branch as well as any commits we’ve done in the meantime in our own `master` branch.
   ```bash
   git log --oneline --decorate --graph --all
   ```
   Expected output (excerpt):
   ```text
   * 8255d41 (HEAD, master) Third commit - first repo
   | * 71b84da (other-master) Last commit - second repo
   | * c99cf5b Fourth commit - second repo
   | * 7011d3d Third commit - second repo
   ```

**Verify:** run `git log --oneline --decorate --graph --all` - expect something like:
```text
* 8255d41 (HEAD, master) Third commit - first repo
| * 71b84da (other-master) Last commit - second repo
| * c99cf5b Fourth commit - second repo
| * 7011d3d Third commit - second repo
|/
* 9a466c5 Second commit
```
