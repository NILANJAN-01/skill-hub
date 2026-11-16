---
name: git-objects
description: "Git internals: blob, tree and commit objects and the .git/objects store. Use when you need to inspect how git stores data."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Git Objects"
  category: git-internals
  source: "Pro Git, 2nd edition"
  pages: "421-431"
---

# Git Objects

The next type of Git object we’ll examine is the tree, which solves the problem of storing the filename and also allows you to store a group of files together.

_Built from "Pro Git" (pages 421-431) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **git objects** (git objects, tree object, git cat-file, git hash-object, git object database).
- The user wants to run or understand `git hash-object -w`.
- The user wants to run or understand `git cat-file -p`.
- The user wants to run or understand `find -type`.
- The user wants to run or understand `echo`.
- The next type of Git object we’ll examine is the tree, which solves the problem of storing the filename and also allows you to store a group of files together.

## When NOT to use

- For packfiles, use the `git-packfiles` skill instead.
- For git references, use the `git-references` skill instead.
- For branches in a nutshell, use the `git-branches-in-a-nutshell` skill instead.

## Key concepts

- As a demonstration, let’s look at the plumbing command `git hash-object`, which takes some data, stores it in your `.git/objects` directory (the object database), and gives you back the unique key that now refers to that data object.
- Once you have content in your object database, you can examine that content with the `git cat-file` command.
- All the content is stored as tree and blob objects, with trees corresponding to UNIX directory entries and blobs corresponding more or less to inodes or file contents.
- A single tree object contains one or more entries, each of which is the SHA-1 hash of a blob or subtree with its associated mode, type, and filename.
- This is essentially what Git does when you run the `git add` and `git commit` commands — it stores blobs for the files that have changed, updates the index, writes out trees, and writes commit objects that reference the top-level trees and the commits that came immediately before them.
- These three main Git objects — the blob, the tree, and the commit — are initially stored as separate files in your `.git/objects` directory.
- We mentioned earlier that there is a header stored with every object you commit to your Git object database.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Git Objects

**Goal:** As a demonstration, let’s look at the plumbing command `git hash-object`, which takes some data, stores it in your `.git/objects` directory (the object database), and gives you back the unique key that now refers to that data object.

**Steps:**

1. First, you initialize a new Git repository and verify that there is (predictably) nothing in the `objects` directory:
   ```bash
   git init test
   cd test
   find .git/objects
   find .git/objects -type f
   ```
   Expected output (excerpt):
   ```text
   Initialized empty Git repository in /tmp/test/.git/
   .git/objects
   .git/objects/info
   .git/objects/pack
   ```
2. Now, let’s use `git hash-object` to create a new data object and manually store it in your new Git database:
   ```bash
   echo 'test content' | git hash-object -w --stdin
   ```
3. Run:
   ```text
   d670460b4b4aece5915caf5c68d12f560a9fe3e4
   ```
4. Now you can see how Git has stored your data:
   ```bash
   find .git/objects -type f
   ```
   Expected output (excerpt):
   ```text
   .git/objects/d6/70460b4b4aece5915caf5c68d12f560a9fe3e4
   ```
5. Passing `-p` to `cat-file` instructs the command to first figure out the type of content, then display it appropriately:
   ```bash
   git cat-file -p d670460b4b4aece5915caf5c68d12f560a9fe3e4
   ```
   Expected output (excerpt):
   ```text
   test content
   ```
6. First, create a new file and save its contents in your database:
   ```bash
   echo 'version 1' > test.txt
   git hash-object -w test.txt
   ```
   Expected output (excerpt):
   ```text
   83baae61804e65cc73a7201a7252750c76066a30
   ```

_5 more step(s) in references/procedures.md._

**Verify:** run `git cat-file -t 1f7a7a472abf3dd9643fd615f6da379c4acb3e3a` - expect something like:
```text
blob
```

### Tree Objects

**Goal:** The next type of Git object we’ll examine is the tree, which solves the problem of storing the filename and also allows you to store a group of files together.

**Steps:**

1. For example, let’s say you have a project where the most-recent tree looks something like:
   ```bash
   git cat-file -p master^{tree}
   ```
   Expected output (excerpt):
   ```text
   100644 blob a906cb2a4a904a152e80877d4088654daad0c859      README
   100644 blob 8f94139338f9404f26296befa88755fc2598c289      Rakefile
   040000 tree 99f1a6d12cb4b6f19c8655fca46c3ecf317074e0      lib
   ```
2. Notice that the `lib` subdirectory isn’t a blob but a pointer to another tree:
   ```bash
   git cat-file -p 99f1a6d12cb4b6f19c8655fca46c3ecf317074e0
   ```
   Expected output (excerpt):
   ```text
   100644 blob 47c6340d6459e05787f644c2447d2595f5d3a54b      simplegit.rb
   ```
3. Then, you specify the mode, SHA-1, and filename:
   ```bash
   git update-index --add --cacheinfo 100644 \
   83baae61804e65cc73a7201a7252750c76066a30 test.txt
   ```
4. No `-w` option is needed — calling this command automatically creates a tree object from the state of the index if that tree doesn’t yet exist:
   ```bash
   git write-tree
   git cat-file -p d8329fc1cc938780ffdd9f94e0d364e0ea74f579
   ```
   Expected output (excerpt):
   ```text
   d8329fc1cc938780ffdd9f94e0d364e0ea74f579
   100644 blob 83baae61804e65cc73a7201a7252750c76066a30      test.txt
   ```
5. You can also verify that this is a tree object using the same `git cat-file` command you saw earlier:
   ```bash
   git cat-file -t d8329fc1cc938780ffdd9f94e0d364e0ea74f579
   ```
   Expected output (excerpt):
   ```text
   tree
   ```
6. You’ll now create a new tree with the second version of `test.txt` and a new file as well:
   ```bash
   echo 'new file' > new.txt
   git update-index --cacheinfo 100644 \
   1f7a7a472abf3dd9643fd615f6da379c4acb3e3a test.txt
   git update-index --add new.txt
   ```

_2 more step(s) in references/procedures.md._

**Verify:** run `git cat-file -t d8329fc1cc938780ffdd9f94e0d364e0ea74f579` - expect something like:
```text
tree
```

### Commit Objects

**Goal:** This is the basic information that the commit object stores for you.

**Steps:**

1. Start with the first tree you wrote:
   ```bash
   echo 'First commit' | git commit-tree d8329f
   ```
   Expected output (excerpt):
   ```text
   fdf4fc3344e67ab068f836878b6c4951e3b15f3d
   ```
2. Now you can look at your new commit object with `git cat-file`:
   ```bash
   git cat-file -p fdf4fc3
   ```
   Expected output (excerpt):
   ```text
   tree d8329fc1cc938780ffdd9f94e0d364e0ea74f579
   author Scott Chacon <schacon@gmail.com> 1243040974 -0700
   committer Scott Chacon <schacon@gmail.com> 1243040974 -0700
   First commit
   ```
3. Next, you’ll write the other two commit objects, each referencing the commit that came directly before it:
   ```bash
   echo 'Second commit' | git commit-tree 0155eb -p fdf4fc3
   echo 'Third commit'  | git commit-tree 3c4e9c -p cac0cab
   ```
   Expected output (excerpt):
   ```text
   cac0cab538b970a37ea1e769cbbde608743bc96d
   1a410efbd13591db07496601ebc7a059dd55cfe9
   ```
4. Oddly enough, you have a real Git history now that you can view with the `git log` command, if you run it on the last commit SHA-1:
   ```bash
   git log --stat 1a410e
   ```
   Expected output (excerpt):
   ```text
   commit 1a410efbd13591db07496601ebc7a059dd55cfe9
   Author: Scott Chacon <schacon@gmail.com>
   Date:   Fri May 22 18:15:24 2009 -0700
       Third commit
   ```
5. Run:
   ```text
    1 file changed, 1 insertion(+)
   commit cac0cab538b970a37ea1e769cbbde608743bc96d
   Author: Scott Chacon <schacon@gmail.com>
   Date:   Fri May 22 18:14:29 2009 -0700
       Second commit
    new.txt  | 1 +
    test.txt | 2 +-
    2 files changed, 2 insertions(+), 1 deletion(-)
   commit fdf4fc3344e67ab068f836878b6c4951e3b15f3d
   Author: Scott Chacon <schacon@gmail.com>
   Date:   Fri May 22 18:09:34 2009 -0700
       First commit
    test.txt | 1 +
    1 file changed, 1 insertion(+)
   ```
6. Here are all the objects in the example directory now, commented with what they store:
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

**Verify:** run `git log --stat 1a410e` - expect something like:
```text
commit 1a410efbd13591db07496601ebc7a059dd55cfe9
Author: Scott Chacon <schacon@gmail.com>
Date:   Fri May 22 18:15:24 2009 -0700
    Third commit
 bak/test.txt | 1 +
```

### Object Storage

**Goal:** We mentioned earlier that there is a header stored with every object you commit to your Git object database.

**Steps:**

1. You can start up interactive Ruby mode with the `irb` command:
   ```bash
   irb
   ```
   Expected output (excerpt):
   ```text
   >> content = "what is up, doc?"
   => "what is up, doc?"
   ```
2. To that first part of the header, Git adds a space followed by the size in bytes of the content, and adding a final null byte:
   ```text
   >> header = "blob #{content.bytesize}\0"
   => "blob 16\u0000"
   ```
3. You can calculate the SHA-1 value of a string in Ruby by including the SHA1 digest library with the `require` command and then calling `Digest::SHA1.hexdigest()` with the string:
   ```text
   >> store = header + content
   => "blob 16\u0000what is up, doc?"
   >> require 'digest/sha1'
   => true
   >> sha1 = Digest::SHA1.hexdigest(store)
   => "bd9dbf5aae1a3862dd1526723246b20206e5fc37"
   ```
4. Here we use `echo -n` to prevent adding a newline to the input.
   ```bash
   echo -n "what is up, doc?" | git hash-object --stdin
   ```
   Expected output (excerpt):
   ```text
   bd9dbf5aae1a3862dd1526723246b20206e5fc37
   ```
5. First, you need to require the library and then run `Zlib::Deflate.deflate()` on the content:
   ```text
   >> require 'zlib'
   => true
   >> zlib_content = Zlib::Deflate.deflate(store)
   => "x\x9CK\xCA\xC9OR04c(\xCFH,Q\xC8,V(-\xD0QH\xC9O\xB6\a\x00_\x1C\a\x9D"
   ```
6. Then, open the file with `File.open()` and write out the previously zlib-compressed content to the file with a `write()` call on the resulting file handle:
   ```text
   >> path = '.git/objects/' + sha1[0,2] + '/' + sha1[2,38]
   => ".git/objects/bd/9dbf5aae1a3862dd1526723246b20206e5fc37"
   >> require 'fileutils'
   => true
   >> FileUtils.mkdir_p(File.dirname(path))
   => ".git/objects/bd"
   >> File.open(path, 'w') { |f| f.write zlib_content }
   => 32
   ```

_2 more step(s) in references/procedures.md._

**Verify:** run `git cat-file -p bd9dbf5aae1a3862dd1526723246b20206e5fc37` - expect something like:
```text
what is up, doc?
```

More procedures in [references/procedures.md](references/procedures.md):

- Git Objects
- Tree Objects
- Object Storage

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git cat-file -p` | If you’re using ZSH, the `^` character is used for globbing, so you have to enclose the whole expression in quotes: `git cat-file -p "master^{tree}"`. | `git cat-file -p fdf4fc3` |
| `git write-tree` | Now, you can use `git write-tree` to write the staging area out to a tree object. | `git write-tree` |
| `git hash-object -w` | First, create a new file and save its contents in your database | `git hash-object -w test.txt` |
| `git cat-file -t` | You can have Git tell you the object type of any object in Git, given its SHA-1 key, with `git cat-file -t` | `git cat-file -t 1f7a7a472abf3dd9643fd615f6da379c4acb3e3a` |
| `git init` | First, you initialize a new Git repository and verify that there is (predictably) nothing in the `objects` directory | `git init test` |
| `git update-index --add --cacheinfo` | Then, you specify the mode, SHA-1, and filename | `git update-index --add --cacheinfo 100644 \` |
| `git update-index --cacheinfo` | You’ll now create a new tree with the second version of `test.txt` and a new file as well | `git update-index --cacheinfo 100644 \` |
| `git update-index --add` | You’ll now create a new tree with the second version of `test.txt` and a new file as well | `git update-index --add new.txt` |
| `git read-tree --prefix` | In this case, you can read an existing tree into your staging area as a subtree by using the `--prefix` option with this command | `git read-tree --prefix=bak d8329fc1cc938780ffdd9f94e0d364e0ea74f579` |
| `git log --stat` | Oddly enough, you have a real Git history now that you can view with the `git log` command, if you run it on the last commit SHA-1 | `git log --stat 1a410e` |
| `irb` | You can start up interactive Ruby mode with the `irb` command | `irb` |

## Decision guide

- All Git objects are stored the same way, just with different types – instead of the string blob, the header will begin with commit or tree.

## Troubleshooting

- **Note:** In CMD on Windows, the `^` character is used for escaping, so you have to double it to avoid this: `git cat-file -p master^^{tree}`. When using PowerShell, parameters using `{}` characters have to be quoted to avoid the parameter being parsed incorrectly: `git cat-file -p 'master^{tree}'`.
- **Note:** You will get a different hash value because of different creation time and author data. Moreover, while in principle any commit object can be reproduced precisely given that data, historical details of this book’s construction mean that the printed commit hashes might not correspond to the given commits. Replace commit and tag hashes with your own checksums further in this chapter.

## Related skills

- `git-packfiles` - Packfiles
- `git-references` - Git References
- `git-branches-in-a-nutshell` - Branches in a Nutshell
- `git-reset-demystified` - Reset Demystified

## Source

"Pro Git", pages 421-431. Sections: Git Objects; Git Objects > Tree Objects; Git Objects > Commit Objects; Git Objects > Object Storage.
