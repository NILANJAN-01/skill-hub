# More procedures: Viewing the Commit History

### Viewing the Commit History

**Goal:** The `oneline` value for this option prints each commit on a single line, which is useful if you’re looking at a lot of commits.

**Steps:**

1. To get the project, run:
   ```bash
   git clone https://github.com/schacon/simplegit-progit
   ```
2. When you run `git log` in this project, you should get output that looks something like this:
   ```bash
   git log
   ```
   Expected output (excerpt):
   ```text
   commit ca82a6dff817ec66f44342007202690a93763949
   Author: Scott Chacon <schacon@gee-mail.com>
   Date:   Mon Mar 17 21:52:11 2008 -0700
       Change version number
   ```
3. You can also limit the number of log entries displayed, such as using `-2` to show only the last two entries.
   ```bash
   git log -p -2
   ```
   Expected output (excerpt):
   ```text
   commit ca82a6dff817ec66f44342007202690a93763949
   Author: Scott Chacon <schacon@gee-mail.com>
   Date:   Mon Mar 17 21:52:11 2008 -0700
       Change version number
   ```
4. For example, if you want to see some abbreviated stats for each commit, you can use the `--stat` option:
   ```bash
   git log --stat
   ```
   Expected output (excerpt):
   ```text
   commit ca82a6dff817ec66f44342007202690a93763949
   Author: Scott Chacon <schacon@gee-mail.com>
   Date:   Mon Mar 17 21:52:11 2008 -0700
       Change version number
   ```
5. In addition, the `short`, `full`, and `fuller` values show the output in roughly the same format but with less or more information, respectively:
   ```bash
   git log --pretty=oneline
   ```
   Expected output (excerpt):
   ```text
   ca82a6dff817ec66f44342007202690a93763949 Change version number
   085bb3bcb608e1e8451d4b2432f8ecbe6306e7e7 Remove unnecessary test
   a11bef06a3f659402fe7563abf99ad00de2209e6 Initial commit
   ```
6. This is especially useful when you’re generating output for machine parsing — because you specify the format explicitly, you know it won’t change with updates to Git:
   ```bash
   git log --pretty=format:"%h - %an, %ar : %s"
   ```
   Expected output (excerpt):
   ```text
   ca82a6d - Scott Chacon, 6 years ago : Change version number
   085bb3b - Scott Chacon, 6 years ago : Remove unnecessary test
   a11bef0 - Scott Chacon, 6 years ago : Initial commit
   ```
7. This option adds a nice little ASCII graph showing your branch and merge history:
   ```bash
   git log --pretty=format:"%h %s" --graph
   ```
   Expected output (excerpt):
   ```text
   * 2d3acf9 Ignore errors from SIGCHLD on trap
   *  5e3ee11 Merge branch 'master' of https://github.com/dustin/grit.git
   |\
   | * 420eac9 Add method for getting the current branch
   ```
8. Run:
   ```text
   * | 5a09431 Add timeout protection to grit
   * | e1193f8 Support for heads with slashes in them
   |/
   * d6016bc Require time for xmlschema
   *  11d191e Merge branch 'defunkt' into local
   ```

**Verify:** run `git log --pretty=format:"%h %s" --graph` - expect something like:
```text
* 2d3acf9 Ignore errors from SIGCHLD on trap
*  5e3ee11 Merge branch 'master' of https://github.com/dustin/grit.git
|\
| * 420eac9 Add method for getting the current branch
* | 30e367c Timeout code and tests
```
