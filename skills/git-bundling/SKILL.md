---
name: git-bundling
description: "Bundling playbook extracted from \"Pro Git\". The first command is the bundle verify command that will make sure the file is actually a valid Git bundle and that you have all the necessary ancestors to reconstitute it properly. Use when the user asks about bundling, git bundle, covered the common, range of commits, data, send, access; or mentions git bundle, git log --oneline, git log, git clone, cd repo, git fetch; or hits errors like \"error: Repository lacks these prerequisite commits:\"."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Bundling"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "324-328"
---

# Bundling

The first command is the `bundle verify` command that will make sure the file is actually a valid Git bundle and that you have all the necessary ancestors to reconstitute it properly.

_Built from "Pro Git" (pages 324-328) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **bundling** (git bundle, covered the common, range of commits, data, send).
- The user wants to run or understand `git bundle`.
- The user wants to run or understand `git log --oneline`.
- The user wants to run or understand `git log`.
- The user wants to run or understand `git clone`.
- The user sees an error like `error: Repository lacks these prerequisite commits:`.
- If you want to send that repository to someone and you don’t have access to a repository to push to, or simply don’t want to set one up, you can bundle it with `git bundle create`.
- The point is to see what can be pulled in, so you can use the `fetch` or `pull` commands to import commits from this bundle.

## When NOT to use

- For contributing to a project, use the `git-distributed-git-contributing-to-a-project` skill instead.
- For working with remotes, use the `git-working-with-remotes` skill instead.
- For maintaining a project, use the `git-distributed-git-maintaining-a-project` skill instead.

## Key concepts

- This is where the `git bundle` command can be helpful.
- The `bundle` command will package up everything that would normally be pushed over the wire with a `git push` command into a binary file that you can email to someone or put on a flash drive, then unbundle into another repository.
- If you want to send that repository to someone and you don’t have access to a repository to push to, or simply don’t want to set one up, you can bundle it with `git bundle create`.
- With the `bundle` command you need to list out every reference or specific range of commits that you want to be included.
- We do that with the `git bundle create` command, giving it a filename we want our bundle to be and the range of commits we want to go into it.
- If the bundler had created a bundle of just the last two commits they had done, rather than all three, the original repository would not be able to import it, since it is missing requisite history.
- The point is to see what can be pulled in, so you can use the `fetch` or `pull` commands to import commits from this bundle.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Bundling

**Goal:** If you want to send that repository to someone and you don’t have access to a repository to push to, or simply don’t want to set one up, you can bundle it with `git bundle create`.

**Steps:**

1. Let’s say you have a repository with two commits:
   ```bash
   git log
   ```
   Expected output (excerpt):
   ```text
   commit 9a466c572fe88b195efd356c3f2bbeccdb504102
   Author: Scott Chacon <schacon@gmail.com>
   Date:   Wed Mar 10 07:34:10 2010 -0800
       Second commit
   ```
2. If you want to send that repository to someone and you don’t have access to a repository to push to, or simply don’t want to set one up, you can bundle it with `git bundle create`.
   ```bash
   git bundle create repo.bundle HEAD master
   ```
   Expected output (excerpt):
   ```text
   Counting objects: 6, done.
   Delta compression using up to 2 threads.
   Compressing objects: 100% (2/2), done.
   Writing objects: 100% (6/6), 441 bytes, done.
   ```
3. You can clone from the binary file into a directory, much like you would from a URL.
   ```bash
   git clone repo.bundle repo
   cd repo
   git log --oneline
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'repo'...
   ...
   ```
4. Run:
   ```text
   9a466c5 Second commit
   b1ec324 First commit
   ```
5. USB stick or email.
   ```bash
   git log --oneline
   ```
   Expected output (excerpt):
   ```text
   71b84da Last commit - second repo
   c99cf5b Fourth commit - second repo
   7011d3d Third commit - second repo
   9a466c5 Second commit
   ```
6. You can test that with the `log` command.
   ```bash
   git log --oneline master ^origin/master
   ```
   Expected output (excerpt):
   ```text
   71b84da Last commit - second repo
   c99cf5b Fourth commit - second repo
   7011d3d Third commit - second repo
   ```

_6 more step(s) in references/procedures.md._

**Verify:** run `git log --oneline --decorate --graph --all` - expect something like:
```text
* 8255d41 (HEAD, master) Third commit - first repo
| * 71b84da (other-master) Last commit - second repo
| * c99cf5b Fourth commit - second repo
| * 7011d3d Third commit - second repo
|/
* 9a466c5 Second commit
```

More procedures in [references/procedures.md](references/procedures.md):

- Bundling

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git bundle` | If you want to send that repository to someone and you don’t have access to a repository to push to, or simply don’t want to set one up, you can bundle it with `git bundle create`. | `git bundle verify ../commits.bundle` |
| `git log --oneline` | You can clone from the binary file into a directory, much like you would from a URL. | `git log --oneline` |
| `git log` | Let’s say you have a repository with two commits | `git log` |
| `git clone` | You can clone from the binary file into a directory, much like you would from a URL. | `git clone repo.bundle repo` |
| `git fetch` | Here we’ll fetch the `master` branch of the bundle to a branch named `other-master` in our repository | `git fetch ../commits.bundle master:other-master` |
| `git log --oneline --decorate` | Now we can see that we have the imported commits on the `other-master` branch as well as any commits we’ve done in the meantime in our own `master` branch. | `git log --oneline --decorate --graph --all` |

## Decision guide

- If you intend for this to be cloned somewhere else, you should add HEAD as a reference as well as we’ve done here.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error: Repository lacks these prerequisite commits:` | However, our first bundle is valid, so we can fetch in commits from it. |


## Related skills

- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-working-with-remotes` - Working with Remotes
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-remote-branches` - Remote Branches

## Source

"Pro Git", pages 324-328. Sections: Bundling.
