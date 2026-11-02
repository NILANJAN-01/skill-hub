---
name: git-references
description: "Git References playbook extracted from \"Pro Git\". That’s basically what a branch in Git is: a simple pointer or reference to the head of a line of work. Use when the user asks about git references, git branch, git object, tag object, head file, history, simple; or mentions cat, git update-ref, git symbolic-ref, git log --pretty, find, find -type; or hits errors like \"fatal: Refusing to point HEAD outside of refs/\"."
---

# Git References

That’s basically what a branch in Git is: a simple pointer or reference to the head of a line of work.

_Built from "Pro Git" (pages 431-435) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **git references** (git branch, git object, tag object, head file, history).
- The user wants to run or understand `cat`.
- The user wants to run or understand `git update-ref`.
- The user wants to run or understand `git symbolic-ref`.
- The user wants to run or understand `git log --pretty`.
- The user sees an error like `fatal: Refusing to point HEAD outside of refs/`.

## When NOT to use

- It’s like a branch reference, but it never moves — it always points to the same commit but gives it a friendlier name.
- That is all a lightweight tag is — a reference that never moves.
- You can `git checkout` to one, but Git won’t symbolically reference HEAD to one, so you’ll never update it with a `commit` command.
- For git objects, use the `git-objects` skill instead.
- For branches in a nutshell, use the `git-branches-in-a-nutshell` skill instead.
- For maintenance and data recovery, use the `git-maintenance-and-data-recovery` skill instead.

## Key concepts

- In Git, these simple names are called “references” or “refs”; you can find the files that contain those
- When you run commands like `git branch <branch>`, Git basically runs that `update-ref` command to add the SHA-1 of the last commit of the branch you’re on into whatever new reference you want to create.
- Usually the HEAD file is a symbolic reference to the branch you’re currently on.
- When you run `git commit`, it creates the commit object, specifying the parent of that commit object to be whatever SHA-1 value the reference in HEAD points to.
- If you create an annotated tag, Git creates a tag object and then writes a reference to point to it rather than directly to the commit.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Git References

**Goal:** That’s basically what a branch in Git is: a simple pointer or reference to the head of a line of work.

**Steps:**

1. In the current project, this directory contains no files, but it does contain a simple structure:
   ```bash
   find .git/refs
   find .git/refs -type f
   ```
   Expected output (excerpt):
   ```text
   .git/refs
   .git/refs/heads
   .git/refs/tags
   ```
2. To create a new reference that will help you remember where your latest commit is, you can technically do something as simple as this:
   ```bash
   echo 1a410efbd13591db07496601ebc7a059dd55cfe9 > .git/refs/heads/master
   ```
3. Now, you can use the head reference you just created instead of the SHA-1 value in your Git commands:
   ```bash
   git log --pretty=oneline master
   ```
   Expected output (excerpt):
   ```text
   1a410efbd13591db07496601ebc7a059dd55cfe9 Third commit
   cac0cab538b970a37ea1e769cbbde608743bc96d Second commit
   fdf4fc3344e67ab068f836878b6c4951e3b15f3d First commit
   ```
4. You aren’t encouraged to directly edit the reference files; instead, Git provides the safer command `git update-ref` to do this if you want to update a reference:
   ```bash
   git update-ref refs/heads/master 1a410efbd13591db07496601ebc7a059dd55cfe9
   ```
5. To create a branch back at the second commit, you can do this:
   ```bash
   git update-ref refs/heads/test cac0ca
   ```
6. Your branch will contain only work from that commit down:
   ```bash
   git log --pretty=oneline test
   ```
   Expected output (excerpt):
   ```text
   cac0cab538b970a37ea1e769cbbde608743bc96d Second commit
   fdf4fc3344e67ab068f836878b6c4951e3b15f3d First commit
   ```

**Verify:** run `git log --pretty=oneline test` - expect something like:
```text
cac0cab538b970a37ea1e769cbbde608743bc96d Second commit
fdf4fc3344e67ab068f836878b6c4951e3b15f3d First commit
```

### The HEAD

**Goal:** Usually the HEAD file is a symbolic reference to the branch you’re currently on.

**Steps:**

1. If you look at the file, you’ll normally see something like this:
   ```bash
   cat .git/HEAD
   ```
   Expected output (excerpt):
   ```text
   ref: refs/heads/master
   ```
2. If you run `git checkout test`, Git updates the file to look like this:
   ```bash
   cat .git/HEAD
   ```
   Expected output (excerpt):
   ```text
   ref: refs/heads/test
   ```
3. You can read the value of your HEAD via this command:
   ```bash
   git symbolic-ref HEAD
   ```
   Expected output (excerpt):
   ```text
   refs/heads/master
   ```
4. You can also set the value of HEAD using the same command:
   ```bash
   git symbolic-ref HEAD refs/heads/test
   cat .git/HEAD
   ```
   Expected output (excerpt):
   ```text
   ref: refs/heads/test
   ```
5. You can’t set a symbolic reference outside of the refs style:
   ```bash
   git symbolic-ref HEAD test
   ```
   Expected output (excerpt):
   ```text
   fatal: Refusing to point HEAD outside of refs/
   ```

### Tags

**Goal:** It’s like a branch reference, but it never moves — it always points to the same commit but gives it a friendlier name.

**Steps:**

1. You can make a lightweight tag by running something like this:
   ```bash
   git update-ref refs/tags/v1.0 cac0cab538b970a37ea1e769cbbde608743bc96d
   ```
2. You can see this by creating an annotated tag (using the `-a` option):
   ```bash
   git tag -a v1.1 1a410efbd13591db07496601ebc7a059dd55cfe9 -m 'Test tag'
   ```
3. Here’s the object SHA-1 value it created:
   ```bash
   cat .git/refs/tags/v1.1
   ```
   Expected output (excerpt):
   ```text
   9585191f37f7b0fb9444f35a9bf50de191beadc2
   ```
4. Now, run `git cat-file -p` on that SHA-1 value:
   ```bash
   git cat-file -p 9585191f37f7b0fb9444f35a9bf50de191beadc2
   ```
   Expected output (excerpt):
   ```text
   object 1a410efbd13591db07496601ebc7a059dd55cfe9
   type commit
   tag v1.1
   tagger Scott Chacon <schacon@gmail.com> Sat May 23 16:48:58 2009 -0700
   ```
5. You can view the public key by running this in a clone of the Git repository:
   ```bash
   git cat-file blob junio-gpg-pub
   ```

**Verify:** run `git cat-file blob junio-gpg-pub`

### Remotes

**Goal:** Remote references differ from branches (`refs/heads` references) mainly in that they’re considered read-only.

**Steps:**

1. For instance, you can add a remote called `origin` and push your `master` branch to it:
   ```bash
   git remote add origin git@github.com:schacon/simplegit-progit.git
   git push origin master
   ```
   Expected output (excerpt):
   ```text
   Counting objects: 11, done.
   Compressing objects: 100% (5/5), done.
   Writing objects: 100% (7/7), 716 bytes, done.
   Total 7 (delta 2), reused 4 (delta 1)
   ```
2. Run:
   ```text
     a11bef0..ca82a6d  master -> master
   ```
3. Then, you can see what the `master` branch on the `origin` remote was the last time you communicated with the server, by checking the `refs/remotes/origin/master` file:
   ```bash
   cat .git/refs/remotes/origin/master
   ```
   Expected output (excerpt):
   ```text
   ca82a6dff817ec66f44342007202690a93763949
   ```

**Verify:** run `cat .git/refs/remotes/origin/master` - expect something like:
```text
ca82a6dff817ec66f44342007202690a93763949
```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git update-ref` | You aren’t encouraged to directly edit the reference files; instead, Git provides the safer command `git update-ref` to do this if you want to update a reference | `git update-ref refs/heads/test cac0ca` |
| `git symbolic-ref` | You can also manually edit this file, but again a safer command exists to do so: `git symbolic-ref`. | `git symbolic-ref HEAD` |
| `git log --pretty` | Now, you can use the head reference you just created instead of the SHA-1 value in your Git commands | `git log --pretty=oneline test` |
| `git tag -a -m` | You can see this by creating an annotated tag (using the `-a` option) | `git tag -a v1.1 1a410efbd13591db07496601ebc7a059dd55cfe9 -m 'Test tag'` |
| `git cat-file -p` | Now, run `git cat-file -p` on that SHA-1 value | `git cat-file -p 9585191f37f7b0fb9444f35a9bf50de191beadc2` |
| `git cat-file` | Now, run `git cat-file -p` on that SHA-1 value | `git cat-file blob junio-gpg-pub` |
| `git remote` | For instance, you can add a remote called `origin` and push your `master` branch to it | `git remote add origin git@github.com:schacon/simplegit-progit.git` |
| `git push` | For instance, you can add a remote called `origin` and push your `master` branch to it | `git push origin master` |

## Decision guide

- Instead, it would be easier if you had a file in which you could store that SHA-1 value under a simple name so you could use that simple name rather than the raw SHA-1 value.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `fatal: Refusing to point HEAD outside of refs/` | See references/source-text.md for this section. |


## Related skills

- `git-objects` - Git Objects
- `git-branches-in-a-nutshell` - Branches in a Nutshell
- `git-maintenance-and-data-recovery` - Maintenance and Data Recovery
- `git-reset-demystified` - Reset Demystified

## Source

"Pro Git", pages 431-435. Sections: Git References; Git References > The HEAD; Git References > Tags; Git References > Remotes.
