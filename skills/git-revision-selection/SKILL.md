---
name: git-revision-selection
description: "Pick commits and ranges: SHA, HEAD~2, HEAD^, .., ..., @{n}. Use when asked what ^, ~ or .. mean."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Revision Selection"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "224-232"
---

# Revision Selection

The last major range-selection syntax is the triple-dot syntax, which specifies all the commits that are reachable by either of two references but not by both of them.

_Built from "Pro Git" (pages 224-232) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **revision selection** (git log, git show head, single commit, objects, repository).
- The user wants to run or understand `git show`.
- The user wants to run or understand `git log`.
- The user wants to run or understand `git log --not`.
- The user wants to run or understand `git log --abbrev-commit --pretty`.
- The double-dot syntax is useful as a shorthand, but perhaps you want to specify more than two branches to indicate your revision, such as seeing what commits are in any of several branches that aren’t in the branch you’re currently on.

## When NOT to use

- For git references, use the `git-references` skill instead.
- For viewing the commit history, use the `git-viewing-the-commit-history` skill instead.
- For git as a client, use the `git-as-a-client` skill instead.

## Key concepts

- Git allows you to refer to a single commit, set of commits, or range of commits in a number of ways.
- One straightforward way to refer to a particular commit is if it’s the commit at the tip of a branch; in that case, you can simply use the branch name in any Git command that expects a reference to a commit.
- The most common range specification is the double-dot syntax.
- This basically asks Git to resolve a range of commits that are reachable from one commit but aren’t reachable from another.
- This command shows you any commits in your current branch that aren’t in the `master` branch on your `origin` remote.
- If you run a `git push` and your current branch is tracking `origin/master`, the commits listed by `git log origin/master..HEAD` are the commits that will be transferred to the server.
- The double-dot syntax is useful as a shorthand, but perhaps you want to specify more than two branches to indicate your revision, such as seeing what commits are in any of several branches that aren’t in the branch you’re currently on.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Short SHA-1

**Goal:** Short SHA-1

**Steps:**

1. For example, to examine a specific commit where you know you added certain functionality, you might first run the `git log` command to locate the commit:
   ```bash
   git log
   ```
   Expected output (excerpt):
   ```text
   commit 734713bc047d87bf7eac9674765ae793478c50d3
   Author: Scott Chacon <schacon@gmail.com>
   Date:   Fri Jan 2 18:32:33 2009 -0800
       Fix refs handling, add gc auto, update tests
   ```
2. Run:
   ```text
       Add some blame and merge stuff
   ```
3. You can inspect that commit with any of the following variations of `git show` (assuming the shorter versions are unambiguous):
   ```bash
   git show 1c002dd4b536e7479fe34593e72e6c6c1819e53b
   git show 1c002dd4b536e7479f
   git show 1c002d
   ```
4. If you pass `--abbrev-commit` to the `git log` command, the output will use shorter values but keep them unique; it defaults to using seven characters but makes them longer if necessary to keep the SHA-1 unambiguous:
   ```bash
   git log --abbrev-commit --pretty=oneline
   ```
   Expected output (excerpt):
   ```text
   ca82a6d Change the version number
   085bb3b Remove unnecessary test code
   a11bef0 Initial commit
   ```

### Branch References

**Goal:** Branch References

**Steps:**

1. For instance, if you want to examine the last commit object on a branch, the following commands are equivalent, assuming that the `topic1` branch points to commit `ca82a6d…`:
   ```bash
   git show ca82a6dff817ec66f44342007202690a93763949
   git show topic1
   ```
2. Here you can run `rev-parse` on your branch.
   ```bash
   git rev-parse topic1
   ```
   Expected output (excerpt):
   ```text
   ca82a6dff817ec66f44342007202690a93763949
   ```

### RefLog Shortnames

**Goal:** RefLog Shortnames

**Steps:**

1. You can see your reflog by using `git reflog`:
   ```bash
   git reflog
   ```
   Expected output (excerpt):
   ```text
   734713b HEAD@{0}: commit: Fix refs handling, add gc auto, update tests
   d921970 HEAD@{1}: merge phedders/rdocs: Merge made by the 'recursive' strategy.
   1c002dd HEAD@{2}: commit: Add some blame and merge stuff
   1c36188 HEAD@{3}: rebase -i (squash): updating HEAD
   ```
2. Run:
   ```text
   1c36188 HEAD@{5}: rebase -i (squash): updating HEAD
   7e05da5 HEAD@{6}: rebase -i (pick): updating HEAD
   ```
3. For example, if you want to see the fifth prior value of the HEAD of your repository, you can use the `@{5}` reference that you see in the reflog output:
   ```bash
   git show HEAD@{5}
   ```
4. For instance, to see where your `master` branch was yesterday, you can type:
   ```bash
   git show master@{yesterday}
   ```
5. To see reflog information formatted like the `git log` output, you can run `git log -g`:
   ```bash
   git log -g master
   ```
   Expected output (excerpt):
   ```text
   commit 734713bc047d87bf7eac9674765ae793478c50d3
   Reflog: master@{0} (Scott Chacon <schacon@gmail.com>)
   Reflog message: commit: Fix refs handling, add gc auto, update tests
   Author: Scott Chacon <schacon@gmail.com>
   ```
6. version of shell history, which emphasizes that what’s there is clearly relevant only for you and your “session”, and has nothing to do with anyone else who might be working on the same machine.
   ```bash
   git show HEAD@{0}     # will NOT work
   git show HEAD@`{0`}   # OK
   git show "HEAD@{0}"   # OK
   ```

### Ancestry References

**Goal:** Ancestry References

**Steps:**

1. Suppose you look at the history of your project:
   ```bash
   git log --pretty=format:'%h %s' --graph
   ```
   Expected output (excerpt):
   ```text
   * 734713b Fix refs handling, add gc auto, update tests
   *   d921970 Merge commit 'phedders/rdocs'
   |\
   | * 35cfb2b Some rdoc changes
   ```
2. Then, you can see the previous commit by specifying `HEAD^`, which means “the parent of HEAD”:
   ```bash
   git show HEAD^
   ```
   Expected output (excerpt):
   ```text
   commit d921970aadf03b3cf0e71becdaab3147ba71cdef
   Merge: 1c002dd... 35cfb2b...
   Author: Scott Chacon <schacon@gmail.com>
   Date:   Thu Dec 11 15:08:43 2008 -0800
   ```
3. Run:
   ```bash
   git show HEAD^     # will NOT work on Windows
   ```
4. Run:
   ```bash
   git show HEAD^^    # OK
   git show "HEAD^"   # OK
   ```
5. You can also specify a number after the `^` to identify which parent you want; for example, `d921970^2` means “the second parent of d921970.” This syntax is useful only for merge commits, which have more than one parent — the first parent of a merge commit is from the branch you were on when you merged (frequently `master`), while the second parent of a merge commit is from the branch that was merged (say, `topic`):
   ```bash
   git show d921970^
   git show d921970^2
   ```
   Expected output (excerpt):
   ```text
   commit 1c002dd4b536e7479fe34593e72e6c6c1819e53b
   Author: Scott Chacon <schacon@gmail.com>
   Date:   Thu Dec 11 14:58:32 2008 -0800
       Add some blame and merge stuff
   ```
6. For example, in the history listed earlier, `HEAD~3` would be:
   ```bash
   git show HEAD~3
   ```
   Expected output (excerpt):
   ```text
   commit 1c3618887afb5fbcbea25b7c013f4e2114448b8d
   Author: Tom Preston-Werner <tom@mojombo.com>
   Date:   Fri Nov 7 13:47:59 2008 -0500
       Ignore *.gem
   ```

_1 more step(s) in references/procedures.md._

**If it fails:** If you place a `^` (caret) at the end of a reference, Git resolves it to mean the parent of that commit.

### Commit Ranges

**Goal:** The double-dot syntax is useful as a shorthand, but perhaps you want to specify more than two branches to indicate your revision, such as seeing what commits are in any of several branches that aren’t in the branch you’re currently on.

**Steps:**

1. You can ask Git to show you a log of just those commits with `master..experiment` — that means “all commits reachable from `experiment` that aren’t reachable from `master`.” For the sake of brevity and clarity in these examples, the letters of the commit objects from the diagram are used in place of the actual log output in the order that they would display:
   ```bash
   git log master..experiment
   ```
   Expected output (excerpt):
   ```text
   D
   C
   ```
2. `experiment..master` shows you everything in `master` not reachable from `experiment`:
   ```bash
   git log experiment..master
   ```
   Expected output (excerpt):
   ```text
   F
   E
   ```
3. Another frequent use of this syntax is to see what you’re about to push to a remote:
   ```bash
   git log origin/master..HEAD
   ```
4. Thus, the following three commands are equivalent:
   ```bash
   git log refA..refB
   git log ^refA refB
   git log refB --not refA
   ```
5. For instance, if you want to see all commits that are reachable from `refA` or `refB` but not from `refC`, you can use either of:
   ```bash
   git log refA refB ^refC
   git log refA refB --not refC
   ```
6. If you want to see what is in `master` or `experiment` but not any common references, you can run:
   ```bash
   git log master...experiment
   ```
   Expected output (excerpt):
   ```text
   F
   E
   D
   C
   ```

_1 more step(s) in references/procedures.md._

**If it fails:** This basically asks Git to resolve a range of commits that are reachable from one commit but aren’t reachable from another.

More procedures in [references/procedures.md](references/procedures.md):

- Ancestry References
- Commit Ranges

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git show` | You can inspect that commit with any of the following variations of `git show` (assuming the shorter versions are unambiguous) | `git show HEAD^` |
| `git log` | If you run a `git push` and your current branch is tracking `origin/master`, the commits listed by `git log origin/master..HEAD` are the commits that will be transferred to the server. | `git log` |
| `git log --not` | Thus, the following three commands are equivalent | `git log refB --not refA` |
| `git log --abbrev-commit --pretty` | If you pass `--abbrev-commit` to the `git log` command, the output will use shorter values but keep them unique; it defaults to using seven characters but makes them longer if necessary to keep the SHA-1 unambiguous | `git log --abbrev-commit --pretty=oneline` |
| `git rev-parse` | Here you can run `rev-parse` on your branch. | `git rev-parse topic1` |
| `git reflog` | You can see your reflog by using `git reflog` | `git reflog` |
| `git log -g` | To see reflog information formatted like the `git log` output, you can run `git log -g` | `git log -g master` |
| `git log --pretty --graph` | Suppose you look at the history of your project | `git log --pretty=format:'%h %s' --graph` |
| `git log --left-right` | This helps make the output more useful | `git log --left-right master...experiment` |

## Troubleshooting

- **Note:** If you do happen to commit an object that hashes to the same SHA-1 value as a previous different object in your repository, Git will see the previous object already in your Git database, assume it was already written and simply reuse it. If you try to check out that object again at some point, you’ll always get the data of the first object.
- **Tip:** Think of the reflog as Git’s version of shell history If you have a UNIX or Linux background, you can think of the reflog as Git’s
- **Note:** Escaping braces in PowerShell When using PowerShell, braces like `{` and `}` are special characters and must be escaped. You can escape them with a backtick ` or put the commit reference in quotes:
- **Note:** Escaping the caret on Windows On Windows in `cmd.exe`, `^` is a special character and needs to be treated differently. You can either double it or put the commit reference in quotes:

## Related skills

- `git-references` - Git References
- `git-viewing-the-commit-history` - Viewing the Commit History
- `git-as-a-client` - Git as a Client
- `git-branches-in-a-nutshell` - Branches in a Nutshell

## Source

"Pro Git", pages 224-232. Sections: Revision Selection; Revision Selection > Single Revisions; Revision Selection > Short SHA-1; Revision Selection > Branch References; Revision Selection > RefLog Shortnames; Revision Selection > Ancestry References; Revision Selection > Commit Ranges.
