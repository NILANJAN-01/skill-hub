---
name: git-the-refspec
description: "The Refspec playbook extracted from \"Pro Git\". Because the refspec is <src>:<dst>, by leaving off the <src> part, this basically says to make the topic branch on the remote nothing, which deletes it. Use when the user asks about the refspec, git push origin, local git repository, git remote add, small local git, remote server, refspec; or mentions git log, git fetch, git push, git remote, git push --delete; or hits errors like \"! [rejected] master -> origin/mymaster (non fast forward)\"."
---

# The Refspec

Because the refspec is `<src>:<dst>`, by leaving off the `<src>` part, this basically says to make the `topic` branch on the remote nothing, which deletes it.

_Built from "Pro Git" (pages 438-441) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **the refspec** (git push origin, local git repository, git remote add, small local git, remote server).
- The user wants to run or understand `git log`.
- The user wants to run or understand `git fetch`.
- The user wants to run or understand `git push`.
- The user wants to run or understand `git remote`.
- The user sees an error like `! [rejected]        master     -> origin/mymaster  (non fast forward)`.
- If you want to do a one-time only fetch, you can specify the specific refspec on the command line, too.

## When NOT to use

- For remote branches, use the `git-remote-branches` skill instead.
- For working with remotes, use the `git-working-with-remotes` skill instead.
- For git references, use the `git-references` skill instead.

## Key concepts

- The format of the refspec is, first, an optional ``, followed by `<src>:<dst>`, where `<src>` is thepattern for references on the remote side and `<dst>` is where those references will be trackedlocally.
- This is just the default refspec for `git fetch` for that remote.
- If you want to do a one-time only fetch, you can specify the specific refspec on the command line, too.
- You can also specify multiple refspecs.
- You can override that by specifying the `+` in front of the refspec.
- You can also specify multiple refspecs for fetching in your configuration file.
- You accomplish that by using refspecs to push.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git push origin :topic`
  - `git push origin --delete topic`

## Procedures

### The Refspec

**Goal:** If you want to do a one-time only fetch, you can specify the specific refspec on the command line, too.

**Steps:**

1. Suppose you were following along with the last couple sections and had created a small local Git repository, and now wanted to add a remote to it:
   ```bash
   git remote add origin https://github.com/schacon/simplegit-progit
   ```
2. Running the command above adds a section to your repository’s `.git/config` file, specifying the name of the remote (`origin`), the URL of the remote repository, and the refspec to be used for fetching:
   ```ini
   [remote "origin"]
       url = https://github.com/schacon/simplegit-progit
       fetch = +refs/heads/*:refs/remotes/origin/*
   ```
3. So, if there is a `master` branch on the server, you can access the log of that branch locally via any of the following:
   ```bash
   git log origin/master
   git log remotes/origin/master
   git log refs/remotes/origin/master
   ```
4. If you want Git instead to pull down only the `master` branch each time, and not every other branch on the remote server, you can change the fetch line to refer to that branch only:
   ```text
   fetch = +refs/heads/master:refs/remotes/origin/master
   ```
5. To pull the `master` branch on the remote down to `origin/mymaster` locally, you can run:
   ```bash
   git fetch origin master:refs/remotes/origin/mymaster
   ```
6. On the command line, you can pull down several branches like so:
   ```bash
   git fetch origin master:refs/remotes/origin/mymaster \
   topic:refs/remotes/origin/topic
   ```
   Expected output (excerpt):
   ```text
   From git@github.com:schacon/simplegit
    ! [rejected]        master     -> origin/mymaster  (non fast forward)
    * [new branch]      topic      -> origin/topic
   ```

_3 more step(s) in references/procedures.md._

**Verify:** run `git log origin/master`

### Pushing Refspecs

**Goal:** You accomplish that by using refspecs to push.

**Steps:**

1. If the QA team wants to push their `master` branch to `qa/master` on the remote server, they can run:
   ```bash
   git push origin master:refs/heads/qa/master
   ```
2. If they want Git to do that automatically each time they run `git push origin`, they can add a `push` value to their config file:
   ```ini
   [remote "origin"]
       url = https://github.com/schacon/simplegit-progit
       fetch = +refs/heads/*:refs/remotes/origin/*
       push = refs/heads/master:refs/heads/qa/master
   ```

### Deleting References

**Goal:** Because the refspec is `<src>:<dst>`, by leaving off the `<src>` part, this basically says to make the `topic` branch on the remote nothing, which deletes it.

**Steps:**

1. You can also use the refspec to delete references from the remote server by running something like this:
   ```bash
   git push origin :topic
   ```
2. Or you can use the newer syntax (available since Git v1.7.0):
   ```bash
   git push origin --delete topic
   ```

More procedures in [references/procedures.md](references/procedures.md):

- The Refspec

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git log` | So, if there is a `master` branch on the server, you can access the log of that branch locally via any of the following | `git log origin/master` |
| `git fetch` | This is just the default refspec for `git fetch` for that remote. | `git fetch origin master:refs/remotes/origin/mymaster` |
| `git push` | Again, this will cause a `git push origin` to push the local `master` branch to the remote `qa/master` branch by default. | `git push origin :topic` |
| `git remote` | In the default case that is automatically written by a `git remote add origin` command, Git fetches all the references under `refs/heads/` on the server and writes them to `refs/remotes/origin/` locally. | `git remote add origin https://github.com/schacon/simplegit-progit` |
| `git push --delete` | Or you can use the newer syntax (available since Git v1.7.0) | `git push origin --delete topic` |

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `! [rejected]        master     -> origin/mymaster  (non fast forward)` | In this case, the `master` branch pull was rejected because it wasn’t listed as a fast-forward reference. |

- **Note:** You cannot use the refspec to fetch from one repository and push to another one. For an example to do so, refer to Keep your GitHub public repository up-to-date.

## Related skills

- `git-remote-branches` - Remote Branches
- `git-working-with-remotes` - Working with Remotes
- `git-references` - Git References
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project

## Source

"Pro Git", pages 438-441. Sections: The Refspec; The Refspec > Pushing Refspecs; The Refspec > Deleting References.
