---
name: git-configuration
description: "Git Configuration playbook extracted from \"Pro Git\". As you read briefly in Getting Started, you can specify Git configuration settings with the git config command. Use when the user asks about git configuration, git config, git diff, place git, git automatically, configuration, git rebase; or mentions git config --global, cat, git config --system, git chekcout, chmod, git apply --whitespace; or hits errors like \"WARNING: You called a Git command named 'chekcout', which does not exist.\"."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git Configuration"
  category: git-customization
  source: "Pro Git, 2nd edition"
  pages: "342-352"
---

# Git Configuration

As you read briefly in Getting Started, you can specify Git configuration settings with the `git config` command.

_Built from "Pro Git" (pages 342-352) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **git configuration** (git config, git diff, place git, git automatically, configuration).
- The user wants to run or understand `git config --global`.
- The user wants to run or understand `cat`.
- The user wants to run or understand `git config --system`.
- The user wants to run or understand `git chekcout`.
- The user sees an error like `WARNING: You called a Git command named 'chekcout', which does not exist.`.

## When NOT to use

- For first-time git setup, use the `git-first-time-git-setup` skill instead.
- For setup and config, use the `git-setup-and-config` skill instead.
- For an example git-enforced policy, use the `git-an-example-git-enforced-policy` skill instead.

## Key concepts

- The next place Git looks is the `~/.gitconfig` (or `~/.config/git/config`) file, which is specific to each user.
- If you set this to the path of a file on your system, Git will use that file as the default initial message when you commit.
- If your team has a commit-message policy, then putting a template for that policy on your system and configuring Git to use it by default can help increase the chance of that policy being followed regularly.
- Git comes preset to use a number of other merge-resolution tools without your having to set up the cmd configuration.
- Git has a few configuration options to help with these issues.
- If you’re on a Linux or macOS system that uses LF line endings, then you don’t want Git to automatically convert them when you check out files; however, if a file with CRLF endings accidentally gets introduced, then you may want Git to fix it.
- Git will detect these issues when you run a `git diff` command and try to color them so you can possibly fix them before you commit.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- …and you run `git config --global core.excludesfile ~/.gitignore_global`, Git will never again bother you about those files.
- You’ll rarely want this; in most scenarios, if you want color codes in your redirected output, you can instead pass a `--color` flag to the Git command to force it to use color codes.
- This is generally good policy; but in the case of the rebase, you may determine that you know what you’re doing and can force-update the remote branch with a `-f` flag to your push command.

## Procedures

### Git Configuration

**Goal:** As you read briefly in Getting Started, you can specify Git configuration settings with the `git config` command.

**Steps:**

1. One of the first things you did was set up your name and email address:
   ```bash
   git config --global user.name "John Doe"
   git config --global user.email johndoe@example.com
   ```

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

_5 more step(s) in references/procedures.md._

### Colors in Git

**Goal:** Colors in Git

**Steps:**

1. To turn off all Git’s colored terminal output, do this:
   ```bash
   git config --global color.ui false
   ```
2. Each of these can be set to `true`, `false`, or `always`:
   ```text
   color.branch
   color.diff
   color.interactive
   color.status
   ```
3. For example, to set the meta information in your diff output to blue foreground, black background, and bold text, you can run:
   ```bash
   git config --global color.diff.meta "blue black bold"
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

_5 more step(s) in references/procedures.md._

**Verify:** run `cat /usr/local/bin/extMerge` - expect something like:
```text
#!/bin/sh
/Applications/kdiff3.app/Contents/MacOS/kdiff3 $*
```

**If it fails:** You can also set up a graphical merge-conflict-resolution tool instead of having to resolve conflicts manually.

### Server Configuration

**Goal:** Not nearly as many configuration options are available for the server side of Git, but there are a few interesting ones you may want to take note of.

**Steps:**

1. If you want Git to check object consistency on every push, you can force it to do so by setting `receive.fsckObjects` to true:
   ```bash
   git config --system receive.fsckObjects true
   ```
2. To tell Git to refuse force-pushes, set `receive.denyNonFastForwards`:
   ```bash
   git config --system receive.denyNonFastForwards true
   ```
3. To avoid this, set `receive.denyDeletes` to true:
   ```bash
   git config --system receive.denyDeletes true
   ```

More procedures in [references/procedures.md](references/procedures.md):

- Basic Client Configuration
- External Merge and Diff Tools
- Formatting and Whitespace

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git config --global` | …and you run `git config --global core.excludesfile ~/.gitignore_global`, Git will never again bother you about those files. | `git config --global core.pager ''` |
| `git config --system` | If you want Git to check object consistency on every push, you can force it to do so by setting `receive.fsckObjects` to true | `git config --system receive.fsckObjects true` |
| `git chekcout` | If you mistype a command, it shows you something like this | `git chekcout master` |
| `chmod` | You also need to make sure these tools are executable | `sudo chmod +x /usr/local/bin/extDiff` |
| `git apply --whitespace` | When you’re applying patches, you can ask Git to warn you if it’s applying patches with the specified whitespace issues | `git apply --whitespace=fix <patch>` |
| `man git-config` | If you want to see a list of all the options your version of Git recognizes, you can run | `man git-config` |
| `git commit` | To tell Git to use it as the default message that appears in your editor when you run `git commit`, set the `commit.template` configuration value | `git commit` |
| `git tag -s` | Now, you can sign tags without having to specify your key every time with the `git tag` command | `git tag -s <tag-name>` |
| `git diff` | Git will detect these issues when you run a `git diff` command and try to color them so you can possibly fix them before you commit. | `git diff 32d1776b1^ 32d1776b1` |
| `git mergetool --tool-help` | To see a list of the tools it supports, try this | `git mergetool --tool-help` |

## Decision guide

- The majority of the options are client-side — configuring your personal working preferences.
- If your preferred editor is Emacs or Vim, you know about filenames that end with a `~` or `.swp`.
- A number of options can help you set the coloring to your preference.
- You can also set up a graphical merge-conflict-resolution tool instead of having to resolve conflicts manually.
- If you want to try this out, P4Merge works on all major platforms, so you should be able to do so.
- If you run this instead of setting up the `extMerge` and `extDiff` files, Git will use KDiff3 for merge resolution and the normal Git diff tool for diffs.
- The three that are disabled by default but can be turned on are `indent-with-non-tab`, which looks for lines that begin with spaces instead of tabs (and is controlled by the `tabwidth` option); `tab-in-indent`, which watches for tabs in the indentation portion of a line; and `cr-at-eol`, which tells Git that carriage returns at the end of lines are OK.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `WARNING: You called a Git command named 'chekcout', which does not exist.` | Note that “0.1 seconds” business. |

- **Note:** Git’s configuration files are plain-text, so you can also set these values by manually editing the file and inserting the correct syntax. It’s generally easier to run the `gitconfig` command, though.
- **Note:** For advanced use cases you may want to look up "Conditional includes" in the documentation mentioned above.

## Related skills

- `git-first-time-git-setup` - First-Time Git Setup
- `git-setup-and-config` - Setup and Config
- `git-an-example-git-enforced-policy` - An Example Git-Enforced Policy
- `git-environment-variables` - Environment Variables

## Source

"Pro Git", pages 342-352. Sections: Git Configuration; Git Configuration > Basic Client Configuration; Git Configuration > Colors in Git; Git Configuration > External Merge and Diff Tools; Git Configuration > Formatting and Whitespace; Git Configuration > Server Configuration.
