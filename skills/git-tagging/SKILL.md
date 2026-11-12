---
name: git-tagging
description: "Tags: list, create annotated or lightweight tags, tag an older commit, push tags, delete local and remote tags, check out a tag. Use when the user wants to tag a commit or mark a release version."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Tagging"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "61-66"
---

# Tagging

The `-m` specifies a tagging message, which is stored with the tag.

_Built from "Pro Git" (pages 61-66) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **tagging** (git push, git tag, lightweight tag, remote, tag commits).
- The user wants to run or understand `git tag`.
- The user wants to run or understand `git show`.
- The user wants to run or understand `git push`.
- The user wants to run or understand `git checkout`.
- The user sees an error like `You are in 'detached HEAD' state. You can look around, make experimental`.

## When NOT to use

- For git references, use the `git-references` skill instead.
- For signing your work, use the `git-signing-your-work` skill instead.
- For maintaining a project, use the `git-distributed-git-maintaining-a-project` skill instead.

## Key concepts

- Git supports two types of tags: lightweight and annotated.
- A lightweight tag is very much like a branch that doesn’t change — it’s just a pointer to a specific commit.
- Creating an annotated tag in Git is simple.
- That shows the tagger information, the date the commit was tagged, and the annotation message before showing the commit information.
- Another way to tag commits is with a lightweight tag.
- By default, the `git push` command doesn’t transfer tags to remote servers.
- If you have a lot of tags that you want to push up at once, you can also use the `--tags` option to the `git push` command.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git push origin :refs/tags/v1.4-lw`
  - `git push origin --delete <tagname>`

## Procedures

### Listing Your Tags

**Goal:** Listing Your Tags

**Steps:**

1. Just type `git tag` (with optional `-l` or `--list`):
   ```bash
   git tag
   ```
   Expected output (excerpt):
   ```text
   v1.0
   v2.0
   ```
2. If you’re interested only in looking at the 1.8.5 series, you can run this:
   ```bash
   git tag -l "v1.8.5*"
   ```
   Expected output (excerpt):
   ```text
   v1.8.5
   v1.8.5-rc0
   v1.8.5-rc1
   v1.8.5-rc2
   ```
3. Run:
   ```text
   v1.8.5.1
   v1.8.5.2
   v1.8.5.3
   v1.8.5.4
   v1.8.5.5
   ```

### Annotated Tags

**Goal:** The `-m` specifies a tagging message, which is stored with the tag.

**Steps:**

1. The easiest way is to specify `-a` when you run the `tag` command:
   ```bash
   git tag -a v1.4 -m "my version 1.4"
   git tag
   ```
   Expected output (excerpt):
   ```text
   v0.1
   v1.3
   v1.4
   ```
2. You can see the tag data along with the commit that was tagged by using the `git show` command:
   ```bash
   git show v1.4
   ```
   Expected output (excerpt):
   ```text
   tag v1.4
   Tagger: Ben Straub <ben@straub.cc>
   Date:   Sat May 3 20:19:12 2014 -0700
   ```
3. Run:
   ```text
   my version 1.4
   commit ca82a6dff817ec66f44342007202690a93763949
   Author: Scott Chacon <schacon@gee-mail.com>
   Date:   Mon Mar 17 21:52:11 2008 -0700
       Change version number
   ```

**Verify:** run `git show v1.4` - expect something like:
```text
tag v1.4
Tagger: Ben Straub <ben@straub.cc>
Date:   Sat May 3 20:19:12 2014 -0700
```

### Lightweight Tags

**Goal:** Lightweight Tags

**Steps:**

1. To create a lightweight tag, don’t supply any of the `-a`, `-s`, or `-m` options, just provide a tag name:
   ```bash
   git tag v1.4-lw
   git tag
   ```
   Expected output (excerpt):
   ```text
   v0.1
   v1.3
   v1.4
   v1.4-lw
   ```
2. The command just shows the commit:
   ```bash
   git show v1.4-lw
   ```
   Expected output (excerpt):
   ```text
   commit ca82a6dff817ec66f44342007202690a93763949
   Author: Scott Chacon <schacon@gee-mail.com>
   Date:   Mon Mar 17 21:52:11 2008 -0700
       Change version number
   ```

**Verify:** run `git show v1.4-lw` - expect something like:
```text
commit ca82a6dff817ec66f44342007202690a93763949
Author: Scott Chacon <schacon@gee-mail.com>
Date:   Mon Mar 17 21:52:11 2008 -0700
    Change version number
```

### Tagging Later

**Goal:** Tagging Later

**Steps:**

1. Suppose your commit history looks like this:
   ```bash
   git log --pretty=oneline
   ```
   Expected output (excerpt):
   ```text
   15027957951b64cf874c3557a0f3547bd83b3ff6 Merge branch 'experiment'
   a6b4c97498bd301d84096da251c98a07c7723e65 Create write support
   0d52aaab4479697da7686c15f77a3d64d9165190 One more thing
   6d52a271eda8725415634dd79daabbc4d9b6008e Merge branch 'experiment'
   ```
2. Run:
   ```text
   4682c3261057305bdd616e23b64b0857d832627b Add todo file
   166ae0c4d3f420721acbb115cc33848dfcc2121a Create write support
   9fceb02d0ae598e95dc970b74767f19372d61af8 Update rakefile
   964f16d36dfccde844893cac5b347e7b3d44abbc Commit the todo
   8a5cbc430f1a9c3d00faaeffd07798508422908a Update readme
   ```
3. To tag that commit, you specify the commit checksum (or part of it) at the end of the command:
   ```bash
   git tag -a v1.2 9fceb02
   ```
4. You can see that you’ve tagged the commit:
   ```bash
   git tag
   git show v1.2
   ```
   Expected output (excerpt):
   ```text
   v0.1
   v1.2
   v1.3
   v1.4
   ```

**Verify:** run `git tag` - expect something like:
```text
v0.1
v1.2
v1.3
v1.4
v1.4-lw
v1.5
```

### Sharing Tags

**Goal:** Sharing Tags

**Steps:**

1. This process is just like sharing remote branches — you can run `git push origin <tagname>`.
   ```bash
   git push origin v1.5
   ```
   Expected output (excerpt):
   ```text
   Counting objects: 14, done.
   Delta compression using up to 8 threads.
   Compressing objects: 100% (12/12), done.
   Writing objects: 100% (14/14), 2.05 KiB | 0 bytes/s, done.
   ```
2. Run:
   ```text
   To git@github.com:schacon/simplegit.git
    * [new tag]         v1.5 -> v1.5
   ```
3. This will transfer all of your tags to the remote server that are not already there.
   ```bash
   git push origin --tags
   ```
   Expected output (excerpt):
   ```text
   Counting objects: 1, done.
   Writing objects: 100% (1/1), 160 bytes | 0 bytes/s, done.
   Total 1 (delta 0), reused 0 (delta 0)
   To git@github.com:schacon/simplegit.git
   ```

More procedures in [references/procedures.md](references/procedures.md):

- Deleting Tags
- Checking out Tags

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git tag` | To delete a tag on your local repository, you can use `git tag -d <tagname>`. | `git tag` |
| `git show` | This time, if you run `git show` on the tag, you don’t see the extra tag information. | `git show v1.4` |
| `git push` | The first variation is `git push <remote> :refs/tags/<tagname>` | `git push origin v1.5` |
| `git checkout` | If you want to view the versions of files a tag is pointing to, you can do a `git checkout` of that tag, although this puts your repository in “detached HEAD” state, which has some ill side effects | `git checkout v2.0.0` |
| `git tag -l` | If you’re interested only in looking at the 1.8.5 series, you can run this | `git tag -l "v1.8.5*"` |
| `git tag -a -m` | The easiest way is to specify `-a` when you run the `tag` command | `git tag -a v1.4 -m "my version 1.4"` |
| `git log --pretty` | Suppose your commit history looks like this | `git log --pretty=oneline` |
| `git tag -a` | To tag that commit, you specify the commit checksum (or part of it) at the end of the command | `git tag -a v1.2 9fceb02` |
| `git push --tags` | This will transfer all of your tags to the remote server that are not already there. | `git push origin --tags` |
| `git tag -d` | To delete a tag on your local repository, you can use `git tag -d <tagname>`. | `git tag -d v1.4-lw` |
| `git push --delete` | The second (and more intuitive) way to delete a remote tag is with | `git push origin --delete <tagname>` |
| `git checkout -b` | Thus, if you need to make changes — say you’re fixing a bug on an older version, for instance — you will generally want to create a branch | `git checkout -b version2 v2.0.0` |

## Decision guide

- If you do this and make a commit, your `version2` branch will be slightly different than your `v2.0.0` tag since it will move forward with your new changes, so do be careful.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `You are in 'detached HEAD' state. You can look around, make experimental` | Thus, if you need to make changes — say you’re fixing a bug on an older version, for instance — you will generally want to create a branch: |

- **Note:** Listing tag wildcards requires `-l` or `--list` option If you want just the entire list of tags, running the command `git tag` implicitly assumes you want a listing and provides one; the use of `-l` or `--list` in this case is optional.
- **Note:** `git push` pushes both types of tags `git push <remote> --tags` will push both lightweight and annotated tags. There is currently no option to push only lightweight tags, but if you use `git push <remote>--follow-tags` only annotated tags will be pushed to the remote.

## Related skills

- `git-references` - Git References
- `git-signing-your-work` - Signing Your Work
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-remote-branches` - Remote Branches

## Source

"Pro Git", pages 61-66. Sections: Tagging; Tagging > Listing Your Tags; Tagging > Creating Tags; Tagging > Annotated Tags; Tagging > Lightweight Tags; Tagging > Tagging Later; Tagging > Sharing Tags; Tagging > Deleting Tags; Tagging > Checking out Tags.
