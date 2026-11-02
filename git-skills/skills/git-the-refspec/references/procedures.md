# More procedures: The Refspec

### The Refspec

**Goal:** If you want to do a one-time only fetch, you can specify the specific refspec on the command line, too.

**Steps:**

1. Suppose you were following along with the last couple sections and had created a small local Git repository, and now wanted to add a remote to it:
   ```bash
   git remote add origin https://github.com/schacon/simplegit-progit
   ```
2. Running the command above adds a section to your repository’s `.git/config` file, specifying the name of the remote (`origin`), the URL of the remote repository, and the refspec to be used for fetching:
   ```ini
   [remote "origin"]
       url = https://github.com/schacon/simplegit-progit
       fetch = +refs/heads/*:refs/remotes/origin/*
   ```
3. So, if there is a `master` branch on the server, you can access the log of that branch locally via any of the following:
   ```bash
   git log origin/master
   git log remotes/origin/master
   git log refs/remotes/origin/master
   ```
4. If you want Git instead to pull down only the `master` branch each time, and not every other branch on the remote server, you can change the fetch line to refer to that branch only:
   ```text
   fetch = +refs/heads/master:refs/remotes/origin/master
   ```
5. To pull the `master` branch on the remote down to `origin/mymaster` locally, you can run:
   ```bash
   git fetch origin master:refs/remotes/origin/mymaster
   ```
6. On the command line, you can pull down several branches like so:
   ```bash
   git fetch origin master:refs/remotes/origin/mymaster \
   topic:refs/remotes/origin/topic
   ```
   Expected output (excerpt):
   ```text
   From git@github.com:schacon/simplegit
    ! [rejected]        master     -> origin/mymaster  (non fast forward)
    * [new branch]      topic      -> origin/topic
   ```
7. If you want to always fetch the `master` and `experiment` branches from the `origin` remote, add two lines:
   ```ini
   [remote "origin"]
       url = https://github.com/schacon/simplegit-progit
       fetch = +refs/heads/master:refs/remotes/origin/master
       fetch = +refs/heads/experiment:refs/remotes/origin/experiment
   ```
8. Since Git 2.6.0 you can use partial globs in the pattern to match multiple branches, so this works:
   ```text
   fetch = +refs/heads/qa*:refs/remotes/origin/qa*
   ```
9. If you have a QA team that pushes a series of branches, and you want to get the `master` branch and any of the QA team’s branches but nothing else, you can use a config section like this:
   ```ini
   [remote "origin"]
       url = https://github.com/schacon/simplegit-progit
       fetch = +refs/heads/master:refs/remotes/origin/master
       fetch = +refs/heads/qa/*:refs/remotes/origin/qa/*
   ```

**Verify:** run `git log origin/master`
