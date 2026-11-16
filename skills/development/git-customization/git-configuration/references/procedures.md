# More procedures: Git Configuration

### Basic Client Configuration

**Goal:** The configuration options recognized by Git fall into two categories: client-side and server-side.

**Steps:**

1. If you want to see a list of all the options your version of Git recognizes, you can run:
   ```bash
   man git-config
   ```
2. To change that default to something else, you can use the `core.editor` setting:
   ```bash
   git config --global core.editor emacs
   ```
3. For instance, consider a template file at `~/.gitmessage.txt` that looks like this:
   ```text
   Subject line (try to keep under 50 characters)
   Multi-line description of commit,
   feel free to be detailed.
   [Ticket: X]
   ```
4. To tell Git to use it as the default message that appears in your editor when you run `git commit`, set the `commit.template` configuration value:
   ```bash
   git config --global commit.template ~/.gitmessage.txt
   git commit
   ```
5. Then, your editor will open to something like this for your placeholder commit message when you commit:
   ```text
   Subject line (try to keep under 50 characters)
   Multi-line description of commit,
   feel free to be detailed.
   [Ticket: X]
   # Please enter the commit message for your changes. Lines starting
   # with '#' will be ignored, and an empty message aborts the commit.
   # On branch master
   # Changes to be committed:
   #   (use "git reset HEAD <file>..." to unstage)
   #
   # modified:   lib/test.rb
   #
   ~
   ~
   ".git/COMMIT_EDITMSG" 14L, 297C
   ```
6. You can set it to `more` or to your favorite pager (by default, it’s `less`), or you can turn it off by setting it to a blank string:
   ```bash
   git config --global core.pager ''
   ```
7. Set your key ID like so:
   ```bash
   git config --global user.signingkey <gpg-key-id>
   ```
8. Now, you can sign tags without having to specify your key every time with the `git tag` command:
   ```bash
   git tag -s <tag-name>
   ```
9. If you create a `~/.gitignore_global` file with these contents:
   ```text
   *~
   .*.swp
   .DS_Store
   ```
10. If you mistype a command, it shows you something like this:
   ```bash
   git chekcout master
   ```
   Expected output (excerpt):
   ```text
   git: 'chekcout' is not a git command. See 'git --help'.
   The most similar command is
       checkout
   ```
11. If you set `help.autocorrect` to 1, Git will actually run this command for you:
   ```bash
   git chekcout master
   ```
   Expected output (excerpt):
   ```text
   WARNING: You called a Git command named 'chekcout', which does not exist.
   Continuing under the assumption that you meant 'checkout'
   in 0.1 seconds automatically...
   ```

### External Merge and Diff Tools

**Goal:** Git comes preset to use a number of other merge-resolution tools without your having to set up the cmd configuration.

**Steps:**

1. Set up a merge wrapper script named `extMerge` that calls your binary with all the arguments provided:
   ```bash
   cat /usr/local/bin/extMerge
   ```
   Expected output (excerpt):
   ```text
   #!/bin/sh
   /Applications/p4merge.app/Contents/MacOS/p4merge $*
   ```
2. By default, Git passes the following arguments to the diff program:
   ```text
   path old-file old-hex old-mode new-file new-hex new-mode
   ```
3. Because you only want the `old-file` and `new-file` arguments, you use the wrapper script to pass the ones you need.
   ```bash
   cat /usr/local/bin/extDiff
   ```
   Expected output (excerpt):
   ```text
   #!/bin/sh
   [ $# -eq 7 ] && /usr/local/bin/extMerge "$2" "$5"
   ```
4. You also need to make sure these tools are executable:
   ```bash
   sudo chmod +x /usr/local/bin/extMerge
   sudo chmod +x /usr/local/bin/extDiff
   ```
5. So, you can either run four config commands:
   ```bash
   git config --global merge.tool extMerge
   git config --global mergetool.extMerge.cmd \
   'extMerge "$BASE" "$LOCAL" "$REMOTE" "$MERGED"'
   git config --global mergetool.extMerge.trustExitCode false
   git config --global diff.external extDiff
   ```
6. or you can edit your `~/.gitconfig` file to add these lines:
   ```ini
   [merge]
     tool = extMerge
   [mergetool "extMerge"]
     cmd = extMerge "$BASE" "$LOCAL" "$REMOTE" "$MERGED"
     trustExitCode = false
   [diff]
     external = extDiff
   ```
7. After all this is set, if you run diff commands such as this:
   ```bash
   git diff 32d1776b1^ 32d1776b1
   ```
8. For example, to change your `extDiff` and `extMerge` tools to run the KDiff3 tool instead, all you have to do is edit your `extMerge` file:
   ```bash
   cat /usr/local/bin/extMerge
   ```
   Expected output (excerpt):
   ```text
   #!/bin/sh
   /Applications/kdiff3.app/Contents/MacOS/kdiff3 $*
   ```
9. To see a list of the tools it supports, try this:
   ```bash
   git mergetool --tool-help
   ```
   Expected output (excerpt):
   ```text
   'git mergetool --tool=<tool>' may be set to one of the following:
           emerge
           gvimdiff
   ```
10. Run:
   ```text
           gvimdiff2
           opendiff
           p4merge
           vimdiff
           vimdiff2
   The following tools are valid, but not currently available:
           araxis
           bc3
           codecompare
           deltawalker
           diffmerge
           diffuse
           ecmerge
           kdiff3
           meld
           tkdiff
           tortoisemerge
           xxdiff
   Some of the tools listed above only work in a windowed
   environment. If run in a terminal-only session, they will fail.
   ```
11. If you’re not interested in using KDiff3 for diff but rather want to use it just for merge resolution, and the kdiff3 command is in your path, then you can run:
   ```bash
   git config --global merge.tool kdiff3
   ```

**Verify:** run `cat /usr/local/bin/extMerge` - expect something like:
```text
#!/bin/sh
/Applications/kdiff3.app/Contents/MacOS/kdiff3 $*
```

**If it fails:** You can also set up a graphical merge-conflict-resolution tool instead of having to resolve conflicts manually.

### Formatting and Whitespace

**Goal:** Git has a few configuration options to help with these issues.

**Steps:**

1. If you’re on a Windows machine, set it to `true` — this converts LF endings into CRLF when you check out code:
   ```bash
   git config --global core.autocrlf true
   ```
2. You can tell Git to convert CRLF to LF on commit but not the other way around by setting `core.autocrlf` to `input`:
   ```bash
   git config --global core.autocrlf input
   ```
3. If you’re a Windows programmer doing a Windows-only project, then you can turn off this functionality, recording the carriage returns in the repository by setting the config value to `false`:
   ```bash
   git config --global core.autocrlf false
   ```
4. For example, if you want all but `space-before-tab` to be set, you can do this (with `trailing-space` being a short-hand to cover both `blank-at-eol` and `blank-at-eof`):
   ```bash
   git config --global core.whitespace \
   trailing-space,-space-before-tab,indent-with-non-tab,tab-in-indent,cr-at-eol
   ```
5. Or you can specify the customizing part only:
   ```bash
   git config --global core.whitespace \
   -space-before-tab,indent-with-non-tab,tab-in-indent,cr-at-eol
   ```
6. When you’re applying patches, you can ask Git to warn you if it’s applying patches with the specified whitespace issues:
   ```bash
   git apply --whitespace=warn <patch>
   ```
7. Or you can have Git try to automatically fix the issue before applying the patch:
   ```bash
   git apply --whitespace=fix <patch>
   ```

**If it fails:** If you’re on a Linux or macOS system that uses LF line endings, then you don’t want Git to automatically convert them when you check out files; however, if a file with CRLF endings accidentally gets introduced, then you may want Git to fix it.
