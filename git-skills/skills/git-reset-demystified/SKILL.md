---
name: git-reset-demystified
description: "Reset Demystified playbook extracted from \"Pro Git\". Like reset, checkout manipulates the three trees, and it is a bit different depending on whether you give the command a file path or not. Use when the user asks about reset demystified, head points, git commit, git reset, file, working directory, branch; or mentions git cat-file -p, git ls-tree -r, git ls-files -s, tree."
---

# Reset Demystified

Like `reset`, `checkout` manipulates the three trees, and it is a bit different depending on whether you give the command a file path or not.

_Built from "Pro Git" (pages 257-277) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **reset demystified** (head points, git commit, git reset, file, working directory).
- The user wants to run or understand `git cat-file -p`.
- The user wants to run or understand `git ls-tree -r`.
- The user wants to run or understand `git ls-files -s`.
- The user wants to run or understand `tree`.
- You can use `reset` to quickly and easily squash them into a single commit that makes you look really smart.

## When NOT to use

- For branches in a nutshell, use the `git-branches-in-a-nutshell` skill instead.
- For advanced merging, use the `git-advanced-merging` skill instead.
- For undoing things, use the `git-undoing-things` skill instead.

## Key concepts

- This isn’t the same as changing HEAD itself (which is what `checkout` does); `reset` moves the branch that HEAD is pointing to.
- When you `reset` back to `HEAD~` (the parent of HEAD), you are moving the branch back to where it was, without changing the index or working directory.
- Whereas `reset` will move the branch that HEAD points to, `checkout` will move HEAD itself to point to another branch.
- `reset` will move the branch HEAD points to, `checkout` moves HEAD itself.
- The other way to run `checkout` is with a file path, which, like `reset`, does not move HEAD.
- It is just like `git reset [branch] file` in that it updates the index with that file at that commit, but it also overwrites the file in the working directory.
- It would be exactly like `git reset --hard [branch] file` (if `reset` would let you run that) — it’s not working-directory safe, and it does not move HEAD.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- It’s important to note that this flag (`--hard`) is the only way to make the `reset` command dangerous, and one of the very few cases where Git will actually destroy data.
- Any other invocation of `reset` can be pretty easily undone, but the `--hard` option cannot, since it forcibly overwrites files in the working directory.
- Git DB, and we could get it back by looking at our `reflog`, but if we had not committed it, Git still would have overwritten the file and it would be unrecoverable.
- It is just like `git reset [branch] file` in that it updates the index with that file at that commit, but it also overwrites the file in the working directory.

## Procedures

### The Three Trees

**Goal:** An easier way to think about `reset` and `checkout` is through the mental frame of Git being a content manager of three different trees.

**Steps:**

1. Here is an example of getting the actual directory listing and SHA-1 checksums for each file in the HEAD snapshot:
   ```bash
   git cat-file -p HEAD
   ```
   Expected output (excerpt):
   ```text
   tree cfda3bf379e4f8dba8717dee55aab78aef7f4daf
   author Scott Chacon  1301511835 -0700
   committer Scott Chacon  1301511835 -0700
   initial commit
   ```
2. Run:
   ```bash
   git ls-tree -r HEAD
   ```
   Expected output (excerpt):
   ```text
   100644 blob a906cb2a4a904a152...   README
   100644 blob 8f94139338f9404f2...   Rakefile
   040000 tree 99f1a6d12cb4b6f19...   lib
   ```
3. You then replace some of those files with new versions of them, and `git commit` converts that into the tree for a new commit.
   ```bash
   git ls-files -s
   ```
   Expected output (excerpt):
   ```text
   100644 a906cb2a4a904a152e80877d4088654daad0c859 0   README
   100644 8f94139338f9404f26296befa88755fc2598c289 0   Rakefile
   100644 47c6340d6459e05787f644c2447d2595f5d3a54b 0   lib/simplegit.rb
   ```
4. Think of the working directory as a sandbox, where you can try changes out before committing them to your staging area (index) and then to history.
   ```bash
   tree
   ```
   Expected output (excerpt):
   ```text
   .
   ├── README
   ├── Rakefile
   └── lib
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git cat-file -p` | Here is an example of getting the actual directory listing and SHA-1 checksums for each file in the HEAD snapshot | `git cat-file -p HEAD` |
| `git ls-tree -r` | Here is an example of getting the actual directory listing and SHA-1 checksums for each file in the HEAD snapshot | `git ls-tree -r HEAD` |
| `git ls-files -s` | You then replace some of those files with new versions of them, and `git commit` converts that into the tree for a new commit. | `git ls-files -s` |

## Decision guide

- If we run `git commit` now, it will record a change that reverts that file back to v1, even though we never actually had it in our working directory again.
- If we instead run `git checkout master`, `develop` does not move,

## Related skills

- `git-branches-in-a-nutshell` - Branches in a Nutshell
- `git-advanced-merging` - Advanced Merging
- `git-undoing-things` - Undoing Things
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository

## Source

"Pro Git", pages 257-277. Sections: Reset Demystified; Reset Demystified > The Three Trees; Reset Demystified > The Workflow; Reset Demystified > The Role of Reset; Reset Demystified > Reset With a Path; Reset Demystified > Squashing; Reset Demystified > Check It Out; Reset Demystified > Summary.
