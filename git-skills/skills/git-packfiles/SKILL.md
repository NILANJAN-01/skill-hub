---
name: git-packfiles
description: "Packfiles playbook extracted from \"Pro Git\". The packfile is a single file containing the contents of all the objects that were removed from your filesystem. Use when the user asks about packfiles, git saves objects, git packs objects, test git repository, git compresses, packfile, files; or mentions find -type, git cat-file -p, git cat-file -s, curl, git checkout, git add."
---

# Packfiles

The packfile is a single file containing the contents of all the objects that were removed from your filesystem.

_Built from "Pro Git" (pages 435-438) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **packfiles** (git saves objects, git packs objects, test git repository, git compresses, packfile).
- The user wants to run or understand `find -type`.
- The user wants to run or understand `git cat-file -p`.
- The user wants to run or understand `git cat-file -s`.
- The user wants to run or understand `curl`.

## When NOT to use

- Because you never added them to any commits, they’re considered dangling and aren’t packed up in your new packfile.
- For git objects, use the `git-objects` skill instead.
- For maintenance and data recovery, use the `git-maintenance-and-data-recovery` skill instead.
- For git references, use the `git-references` skill instead.

## Key concepts

- The initial format in which Git saves objects on disk is called a “loose” object format.
- However, occasionally Git packs up several of these objects into a single binary file called a “packfile” in order to save space and be more efficient.
- The other files are your new packfile and an index.
- The index is a file that contains offsets into that packfile so you can quickly seek to a specific object.
- What is cool is that although the objects on disk before you ran the `gc` command were collectively about 15K in size, the new packfile is only 7K.
- When Git packs objects, it looks for files that are named and sized similarly, and stores just the deltas from one version of the file to the next.
- You can look into the packfile and see what Git did to save space.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Packfiles

**Goal:** The packfile is a single file containing the contents of all the objects that were removed from your filesystem.

**Steps:**

1. If you followed all of the instructions in the example from the previous section, you should now have a test Git repository with 11 objects — four blobs, three trees, three commits, and one tag:
   ```bash
   find .git/objects -type f
   ```
   Expected output (excerpt):
   ```text
   .git/objects/01/55eb4229851634a0f03eb265b69f5a2d56f341 # tree 2
   .git/objects/1a/410efbd13591db07496601ebc7a059dd55cfe9 # commit 3
   .git/objects/1f/7a7a472abf3dd9643fd615f6da379c4acb3e3a # test.txt v2
   .git/objects/3c/4e9cd789d88d8d89c1073707c3585e41b0e614 # tree 3
   ```
2. To demonstrate, we’ll add the `repo.rb` file from the Grit library — this is about a 22K source code file:
   ```bash
   curl https://raw.githubusercontent.com/mojombo/grit/master/lib/grit/repo.rb >
   git checkout master
   git add repo.rb
   git commit -m 'Create repo.rb'
   ```
   Expected output (excerpt):
   ```text
   repo.rb
   [master 484a592] Create repo.rb
    3 files changed, 709 insertions(+), 2 deletions(-)
    delete mode 100644 bak/test.txt
   ```
3. If you look at the resulting tree, you can see the SHA-1 value that was calculated for your new `repo.rb` blob object:
   ```bash
   git cat-file -p master^{tree}
   ```
   Expected output (excerpt):
   ```text
   100644 blob fa49b077972391ad58037050f2a75f74e3671e92      new.txt
   100644 blob 033b4468fa6b2a9547a70d88d1bbe8bf3f9ed0d5      repo.rb
   100644 blob e3f094f522629ae358806b17daf78246c27c007b      test.txt
   ```
4. You can then use `git cat-file` to see how large that object is:
   ```bash
   git cat-file -s 033b4468fa6b2a9547a70d88d1bbe8bf3f9ed0d5
   ```
   Expected output (excerpt):
   ```text
   22044
   ```
5. At this point, modify that file a little, and see what happens:
   ```bash
   echo '# testing' >> repo.rb
   git commit -am 'Modify repo.rb a bit'
   ```
   Expected output (excerpt):
   ```text
   [master 2431da6] Modify repo.rb a bit
    1 file changed, 1 insertion(+)
   ```
6. Check the tree created by that last commit, and you see something interesting:
   ```bash
   git cat-file -p master^{tree}
   ```
   Expected output (excerpt):
   ```text
   100644 blob fa49b077972391ad58037050f2a75f74e3671e92      new.txt
   100644 blob b042a60ef7dff760008df33cee372b945b6e884e      repo.rb
   100644 blob e3f094f522629ae358806b17daf78246c27c007b      test.txt
   ```

_6 more step(s) in references/procedures.md._

**Verify:** run `git cat-file -s b042a60ef7dff760008df33cee372b945b6e884e` - expect something like:
```text
22054
```

More procedures in [references/procedures.md](references/procedures.md):

- Packfiles

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git cat-file -p` | If you look at the resulting tree, you can see the SHA-1 value that was calculated for your new `repo.rb` blob object | `git cat-file -p master^{tree}` |
| `git cat-file -s` | You can then use `git cat-file` to see how large that object is | `git cat-file -s 033b4468fa6b2a9547a70d88d1bbe8bf3f9ed0d5` |
| `curl` | To demonstrate, we’ll add the `repo.rb` file from the Grit library — this is about a 22K source code file | `curl https://raw.githubusercontent.com/mojombo/grit/master/lib/grit/repo.rb >` |
| `git checkout` | To demonstrate, we’ll add the `repo.rb` file from the Grit library — this is about a 22K source code file | `git checkout master` |
| `git add` | To demonstrate, we’ll add the `repo.rb` file from the Grit library — this is about a 22K source code file | `git add repo.rb` |
| `git commit -m` | To demonstrate, we’ll add the `repo.rb` file from the Grit library — this is about a 22K source code file | `git commit -m 'Create repo.rb'` |
| `git commit -am` | At this point, modify that file a little, and see what happens | `git commit -am 'Modify repo.rb a bit'` |
| `git gc` | To see what happens, you can manually ask Git to pack up the objects by calling the `git gc` command | `git gc` |
| `git verify-pack -v` | The `git verify-pack` plumbing command allows you to see what was packed up | `git verify-pack -v .git/objects/pack/pack-` |

## Related skills

- `git-objects` - Git Objects
- `git-maintenance-and-data-recovery` - Maintenance and Data Recovery
- `git-references` - Git References
- `git-branches-in-a-nutshell` - Branches in a Nutshell

## Source

"Pro Git", pages 435-438. Sections: Packfiles.
