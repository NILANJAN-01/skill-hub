# More procedures: Revision Selection

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
7. This can also be written `HEAD~~~`, which again is the first parent of the first parent of the first parent:
   ```bash
   git show HEAD~~~
   ```
   Expected output (excerpt):
   ```text
   commit 1c3618887afb5fbcbea25b7c013f4e2114448b8d
   Author: Tom Preston-Werner <tom@mojombo.com>
   Date:   Fri Nov 7 13:47:59 2008 -0500
       Ignore *.gem
   ```

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
7. This helps make the output more useful:
   ```bash
   git log --left-right master...experiment
   ```
   Expected output (excerpt):
   ```text
   < F
   < E
   > D
   > C
   ```

**If it fails:** This basically asks Git to resolve a range of commits that are reachable from one commit but aren’t reachable from another.
