---
name: git-branch-management
description: "List, rename and delete branches, see which are merged or unmerged, rename master to main (git branch -v, --merged, --no-merged, --move, -d). Use when the user wants to list, rename, clean up or delete branches."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Branch Management"
  category: git-branching
  source: "Pro Git, 2nd edition"
  pages: "85-88"
---

# Branch Management

This means that if you commit at this point, the `master` branch will be moved forward with your new work.

_Built from "Pro Git" (pages 85-88) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **branch management** (git branch, branch-management tools, corrected branch, notice, no-merged).
- The user wants to run or understand `git branch --no-merged`.
- The user wants to run or understand `git branch --move`.
- The user wants to run or understand `git branch --all`.
- The user wants to run or understand `git branch`.
- The user sees an error like `error: The branch 'testing' is not fully merged.`.

## When NOT to use

- For remote branches, use the `git-remote-branches` skill instead.
- For working with remotes, use the `git-working-with-remotes` skill instead.
- For basic branching and merging, use the `git-basic-branching-and-merging` skill instead.

## Key concepts

- This replaces your `bad-branch-name` with `corrected-branch-name`, but this change is only local for now.
- Notice that you’re on the branch `corrected-branch-name` and it’s available on the remote.
- There’s no local `master` branch anymore, because it’s renamed to the `main` branch.
- This makes the renamed branch available on the remote.
- Your local `master` branch is gone, as it’s replaced with the `main` branch.
- The `main` branch is present on the remote.
- However, the old `master` branch is still present on the remote.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git push origin --delete bad-branch-name`
  - `git push origin --delete master`
- **Caution (from source):** Do not rename branches that are still in use by other collaborators. Do not rename a branch like master/main/mainline without having read the section Changing the master branch name.
- **Warning (from source):** Changing the name of a branch like master/main/mainline/default will break the integrations, services, helper utilities and build/release scripts that your repository uses. Before you do this, make sure you consult with your collaborators. Also, make sure you do a thorough search through your repo and update any references to the old branch name in your code and scripts.
- Branches on this list without the `*` in front of them are generally fine to delete with `git branch -d`; you’ve already incorporated their work into another branch, so you’re not going to lose anything.
- If you really do want to delete the branch and lose that work, you can force it with `-D`, as the helpful message points out.

## Procedures

### Branch Management

**Goal:** This means that if you commit at this point, the `master` branch will be moved forward with your new work.

**Steps:**

1. If you run it with no arguments, you get a simple listing of your current branches:
   ```bash
   git branch
   ```
   Expected output (excerpt):
   ```text
     iss53
   * master
     testing
   ```
2. To see the last commit on each branch, you can run `git branch -v`:
   ```bash
   git branch -v
   ```
   Expected output (excerpt):
   ```text
     iss53   93b412c Fix javascript issue
   * master  7a98805 Merge branch 'iss53'
     testing 782fd34 Add scott to the author list in the readme
   ```
3. To see which branches are already merged into the branch you’re on, you can run `git branch --merged`:
   ```bash
   git branch --merged
   ```
   Expected output (excerpt):
   ```text
     iss53
   * master
   ```
4. To see all the branches that contain work you haven’t yet merged in, you can run `git branch --no-merged`:
   ```bash
   git branch --no-merged
   ```
   Expected output (excerpt):
   ```text
     testing
   ```
5. Because it contains work that isn’t merged in yet, trying to delete it with `git branch -d` will fail:
   ```bash
   git branch -d testing
   ```
   Expected output (excerpt):
   ```text
   error: The branch 'testing' is not fully merged.
   If you are sure you want to delete it, run 'git branch -D testing'.
   ```
6. The options described above, `--merged` and `--no-merged` will, if not given a commit or branch name as an argument, show you what is, respectively, merged or not merged into your current branch.
   ```bash
   git checkout testing
   git branch --no-merged master
   ```
   Expected output (excerpt):
   ```text
     topicA
     featureB
   ```

### Changing a branch name

**Goal:** You also want to change the branch name on the remote (GitHub, GitLab, other server).

**Steps:**

1. Rename the branch locally with the `git branch --move` command:
   ```bash
   git branch --move bad-branch-name corrected-branch-name
   ```
2. To let others see the corrected branch on the remote, push it:
   ```bash
   git push --set-upstream origin corrected-branch-name
   ```
3. Now we’ll take a brief look at where we are now:
   ```bash
   git branch --all
   ```
   Expected output (excerpt):
   ```text
   * corrected-branch-name
     main
     remotes/origin/bad-branch-name
     remotes/origin/corrected-branch-name
   ```
4. However, the branch with the bad name is also still present there but you can delete it by executing the following command:
   ```bash
   git push origin --delete bad-branch-name
   ```
5. Rename your local `master` branch into `main` with the following command:
   ```bash
   git branch --move master main
   ```
6. This makes the renamed branch available on the remote.
   ```bash
   git push --set-upstream origin main
   ```

_2 more step(s) in references/procedures.md._

More procedures in [references/procedures.md](references/procedures.md):

- Changing a branch name

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git branch --no-merged` | To see all the branches that contain work you haven’t yet merged in, you can run `git branch --no-merged` | `git branch --no-merged` |
| `git branch --move` | Rename the branch locally with the `git branch --move` command | `git branch --move master main` |
| `git push --set-upstream` | To let others see the corrected branch on the remote, push it | `git push --set-upstream origin main` |
| `git branch --all` | Now we’ll take a brief look at where we are now | `git branch --all` |
| `git push --delete` | However, the branch with the bad name is also still present there but you can delete it by executing the following command | `git push origin --delete master` |
| `git branch` | Rename the branch locally with the `git branch --move` command | `git branch` |
| `git branch -v` | To see the last commit on each branch, you can run `git branch -v` | `git branch -v` |
| `git branch --merged` | To see which branches are already merged into the branch you’re on, you can run `git branch --merged` | `git branch --merged` |
| `git branch -d` | Because it contains work that isn’t merged in yet, trying to delete it with `git branch -d` will fail | `git branch -d testing` |
| `git checkout` | The options described above, `--merged` and `--no-merged` will, if not given a commit or branch name as an argument, show you what is, respectively, merged or not merged into your current branch. | `git checkout testing` |

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error: The branch 'testing' is not fully merged.` | If you really do want to delete the branch and lose that work, you can force it with `-D`, as the helpful message points out. |

- **Tip:** You can always provide an additional argument to ask about the merge state with respect to some other branch without checking that other branch out first, as in, what is not merged into the `master` branch?

## Related skills

- `git-remote-branches` - Remote Branches
- `git-working-with-remotes` - Working with Remotes
- `git-basic-branching-and-merging` - Basic Branching and Merging
- `git-branches-in-a-nutshell` - Branches in a Nutshell

## Source

"Pro Git", pages 85-88. Sections: Branch Management; Branch Management > Changing a branch name.
