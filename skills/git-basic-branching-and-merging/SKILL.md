---
name: git-basic-branching-and-merging
description: "Create, switch, merge and delete a branch and resolve a basic conflict. Use when handling branch or merge tasks or CONFLICT (content)."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Basic Branching and Merging"
  category: git-branching
  source: "Pro Git, 2nd edition"
  pages: "76-85"
---

# Basic Branching and Merging

However, before you do that, note that if your working directory or staging area has uncommitted changes that conflict with the branch you’re checking out, Git won’t let you switch branches.

_Built from "Pro Git" (pages 76-85) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **basic branching and merging** (git merge, merge commit, switch back, branch back, conflict).
- The user wants to run or understand `git merge`.
- The user wants to run or understand `git branch -d`.
- The user wants to run or understand `git branch`.
- The user wants to run or understand `git checkout`.
- The user sees an error like `CONFLICT (content): Merge conflict in index.html`.
- If you need to pull it in, you can merge your `master` branch into your `iss53` branch by running `git merge master`, or you can wait to integrate those changes until you decide to pull the `iss53` branch back into `master` later.

## When NOT to use

- For advanced merging, use the `git-advanced-merging` skill instead.
- For branches in a nutshell, use the `git-branches-in-a-nutshell` skill instead.
- For rebasing, use the `git-rebasing` skill instead.

## Key concepts

- You can run your tests, make sure the hotfix is what you want, and finally merge the `hotfix` branch back into your `master` branch to deploy to production.
- Because the commit `C4` pointed to by the branch `hotfix` you merged in was directly ahead of the commit `C2` you’re on, Git simply moves the pointer forward.
- To phrase that another way, when you try to merge one commit with a commit that can be reached by following the first commit’s history, Git simplifies things by moving the pointer forward because there is no divergent work to merge together — this is called a “fast-forward.”
- Your change is now in the snapshot of the commit pointed to by the `master` branch, and you can deploy the fix.
- In order to do that, you’ll merge your `iss53` branch into `master`, much like you merged your `hotfix` branch earlier.
- Because the commit on the branch you’re on isn’t a direct ancestor of the branch you’re merging in, Git has to do some work.
- Instead of just moving the branch pointer forward, Git creates a new snapshot that results from this three-way merge and automatically creates a new commit that points to it.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Basic Branching

**Goal:** To phrase that another way, when you try to merge one commit with a commit that can be reached by following the first commit’s history, Git simplifies things by moving the pointer forward because there is no divergent work to merge together — this is called a “fast-forward.”

**Steps:**

1. To create a new branch and switch to it at the same time, you can run the `gitcheckout` command with the `-b` switch:
   ```bash
   git checkout -b iss53
   ```
   Expected output (excerpt):
   ```text
   Switched to a new branch "iss53"
   ```
2. This is shorthand for:
   ```bash
   git branch iss53
   git checkout iss53
   ```
3. Doing so moves the `iss53` branch forward, because you have it checked out (that is, your `HEAD` is pointing to it):
   ```bash
   vim index.html
   git commit -a -m 'Create new footer [issue 53]'
   ```
4. For now, let’s assume you’ve committed all your changes, so you can switch back to your `master` branch:
   ```bash
   git checkout master
   ```
   Expected output (excerpt):
   ```text
   Switched to branch 'master'
   ```
5. Let’s create a `hotfix` branch on which to work until it’s completed:
   ```bash
   git checkout -b hotfix
   vim index.html
   git commit -a -m 'Fix broken email address'
   ```
   Expected output (excerpt):
   ```text
   Switched to a new branch 'hotfix'
   [hotfix 1fb7853] Fix broken email address
    1 file changed, 2 insertions(+)
   ```
6. You do this with the `git merge` command:
   ```bash
   git checkout master
   git merge hotfix
   ```
   Expected output (excerpt):
   ```text
   Updating f42c576..3a0874c
   Fast-forward
    index.html | 2 ++
    1 file changed, 2 insertions(+)
   ```

_2 more step(s) in references/procedures.md._

**If it fails:** Now you get the call that there is an issue with the website, and you need to fix it immediately.

### Basic Merging

**Goal:** In order to do that, you’ll merge your `iss53` branch into `master`, much like you merged your `hotfix` branch earlier.

**Steps:**

1. All you have to do is check out the branch you wish to merge into and then run the `git merge` command:
   ```bash
   git checkout master
   git merge iss53
   ```
   Expected output (excerpt):
   ```text
   Switched to branch 'master'
   Merge made by the 'recursive' strategy.
   index.html |    1 +
   1 file changed, 1 insertion(+)
   ```
2. You can close the issue in your issue-tracking system, and delete the branch:
   ```bash
   git branch -d iss53
   ```

### Basic Merge Conflicts

**Goal:** This means the version in `HEAD` (your `master` branch, because that was what you had checked out when you ran your merge command) is the top part of that block (everything above the `=======`), while the version in your `iss53` branch looks like everything in the bottom part.

**Steps:**

1. If your fix for issue #53 modified the same part of a file as the `hotfix` branch, you’ll get a merge conflict that looks something like this:
   ```bash
   git merge iss53
   ```
   Expected output (excerpt):
   ```text
   Auto-merging index.html
   CONFLICT (content): Merge conflict in index.html
   Automatic merge failed; fix conflicts and then commit the result.
   ```
2. If you want to see which files are unmerged at any point after a merge conflict, you can run `git status`:
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   You have unmerged paths.
     (fix conflicts and run "git commit")
   Unmerged paths:
   ```
3. Your file contains a section that looks something like this:
   ```text
   <<<<<<< HEAD:index.html
   <div id="footer">contact : email.support@github.com</div>
   =======
   <div id="footer">
    please contact us at support@github.com
   </div>
   >>>>>>> iss53:index.html
   ```
4. For instance, you might resolve this conflict by replacing the entire block with this:
   ```text
   <div id="footer">
   please contact us at email.support@github.com
   </div>
   ```
5. If you want to use a graphical tool to resolve these issues, you can run `git mergetool`, which fires up an appropriate visual merge tool and walks you through the conflicts:
   ```bash
   git mergetool
   ```
   Expected output (excerpt):
   ```text
   This message is displayed because 'merge.tool' is not configured.
   See 'git mergetool --tool-help' or 'git help config' for more details.
   'git mergetool' will now attempt to use one of the following tools:
   opendiff kdiff3 tkdiff xxdiff meld tortoisemerge gvimdiff diffuse diffmerge ecmerge
   ```
6. You can run `git status` again to verify that all conflicts have been resolved:
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   All conflicts fixed but you are still merging.
     (use "git commit" to conclude merge)
   Changes to be committed:
   ```

_2 more step(s) in references/procedures.md._

**Verify:** run `git status` - expect something like:
```text
On branch master
All conflicts fixed but you are still merging.
  (use "git commit" to conclude merge)
Changes to be committed:
    modified:   index.html
```

**If it fails:** If your fix for issue #53 modified the same part of a file as the `hotfix` branch, you’ll get a merge conflict that looks something like this:

More procedures in [references/procedures.md](references/procedures.md):

- Basic Branching
- Basic Merge Conflicts

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git checkout` | This is shorthand for | `git checkout iss53` |
| `git commit -a -m` | Doing so moves the `iss53` branch forward, because you have it checked out (that is, your `HEAD` is pointing to it) | `git commit -a -m 'Fix broken email address'` |
| `git merge` | If you want to use a graphical tool to resolve these issues, you can run `git mergetool`, which fires up an appropriate visual merge tool and walks you through the conflicts | `git merge iss53` |
| `git checkout -b` | To create a new branch and switch to it at the same time, you can run the `gitcheckout` command with the `-b` switch | `git checkout -b iss53` |
| `git branch -d` | You can delete it with the `-d` option to `gitbranch` | `git branch -d iss53` |
| `git status` | If you want to see which files are unmerged at any point after a merge conflict, you can run `git status` | `git status` |
| `git branch` | This is shorthand for | `git branch iss53` |
| `git mergetool` | If you want to use a graphical tool to resolve these issues, you can run `git mergetool`, which fires up an appropriate visual merge tool and walks you through the conflicts | `git mergetool` |

## Decision guide

- Instead of just moving the branch pointer forward, Git creates a new snapshot that results from this three-way merge and automatically creates a new commit that points to it.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `CONFLICT (content): Merge conflict in index.html` | It has paused the process while you resolve the conflict. |

- **Note:** If you need more advanced tools for resolving tricky merge conflicts, we cover more on merging in Advanced Merging.

## Related skills

- `git-advanced-merging` - Advanced Merging
- `git-branches-in-a-nutshell` - Branches in a Nutshell
- `git-rebasing` - Rebasing
- `git-remote-branches` - Remote Branches

## Source

"Pro Git", pages 76-85. Sections: Basic Branching and Merging; Basic Branching and Merging > Basic Branching; Basic Branching and Merging > Basic Merging; Basic Branching and Merging > Basic Merge Conflicts.
