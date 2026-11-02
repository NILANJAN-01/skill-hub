# More procedures: Maintaining a Project

### Managing Pull Requests

**Goal:** For these examples, let’s assume you are “tonychacon” and you’ve created a new Arduino code project named “fade”.

**Steps:**

1. You could technically merge in the Pull Request work with something like this:
   ```bash
   curl https://github.com/tonychacon/fade/pull/1.patch | git am
   ```
2. If we run this command against the “blink” repository we were using earlier, we will get a list of all the branches and tags and other references in the repository.
   ```bash
   git ls-remote https://github.com/schacon/blink
   ```
   Expected output (excerpt):
   ```text
   10d539600d86723087810ec636870a504f4fee4d    HEAD
   10d539600d86723087810ec636870a504f4fee4d    refs/heads/master
   6a83107c62950be9453aac297bb0193fd743cd6e    refs/pull/1/head
   afe83c2d1a70674c9505cc1d8b7d380d5e076ed3    refs/pull/1/merge
   ```
3. Now, you could do something like fetching the reference directly.
   ```bash
   git fetch origin refs/pull/958/head
   ```
   Expected output (excerpt):
   ```text
   From https://github.com/libgit2/libgit2
    * branch            refs/pull/958/head -> FETCH_HEAD
   ```
4. It should look a bit like this:
   ```ini
   [remote "origin"]
       url = https://github.com/libgit2/libgit2
       fetch = +refs/heads/*:refs/remotes/origin/*
   ```
5. That line that begins with `fetch =` is a “refspec.” It’s a way of mapping names on the remote with names in your local `.git` directory.
   ```ini
   [remote "origin"]
       url = https://github.com/libgit2/libgit2.git
       fetch = +refs/heads/*:refs/remotes/origin/*
       fetch = +refs/pull/*/head:refs/remotes/origin/pr/*
   ```
6. That last line tells Git, “All the refs that look like `refs/pull/123/head` should be stored locally like `refs/remotes/origin/pr/123`.” Now, if you save that file, and do a `git fetch`:
   ```bash
   git fetch
   ```
   Expected output (excerpt):
   ```text
   # …
    * [new ref]         refs/pull/1/head -> origin/pr/1
    * [new ref]         refs/pull/2/head -> origin/pr/2
    * [new ref]         refs/pull/4/head -> origin/pr/4
   ```
7. This makes it super easy to try the code from a pull request locally:
   ```bash
   git checkout pr/2
   ```
   Expected output (excerpt):
   ```text
   Checking out files: 100% (3769/3769), done.
   Branch pr/2 set up to track remote branch pr/2 from origin.
   Switched to a new branch 'pr/2'
   ```

**Verify:** run `git ls-remote https://github.com/schacon/blink` - expect something like:
```text
10d539600d86723087810ec636870a504f4fee4d    HEAD
10d539600d86723087810ec636870a504f4fee4d    refs/heads/master
6a83107c62950be9453aac297bb0193fd743cd6e    refs/pull/1/head
afe83c2d1a70674c9505cc1d8b7d380d5e076ed3    refs/pull/1/merge
3c8d735ee16296c242be7a9742ebfbc2665adec1    refs/pull/2/head
15c9f4f80973a2758462ab2066b6ad9fe8dcf03d    refs/pull/2/merge
```

**If it fails:** So if someone opens a Pull Request in our repository and their branch is named `bug-fix` and it points to commit `a5a775`, then in our repository we will not have a `bug-fix` branch (since that’s in their fork), but we will have `pull/<pr#>/head` that points to `a5a775`.
