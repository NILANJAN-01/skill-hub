---
name: git-environment-variables
description: "Environment Variables playbook extracted from \"Pro Git\". Some of Git’s general behavior as a computer program depends on environment variables. Use when the user asks about environment variables, git diff, portable git, git behave, field, object, editor git; or mentions GIT_TRACE=true git, GIT_TRACE_PACK_ACCESS=true git, GIT_TRACE_PACKET=true git, GIT_TRACE_PERFORMANCE=true git, GIT_TRACE_SETUP=true git, GIT_REFLOG_ACTION=\"my --allow-empty -m."
---

# Environment Variables

Some of Git’s general behavior as a computer program depends on environment variables.

_Built from "Pro Git" (pages 453-458) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **environment variables** (git diff, portable git, git behave, field, object).
- The user wants to run or understand `GIT_TRACE=true git`.
- The user wants to run or understand `GIT_TRACE_PACK_ACCESS=true git`.
- The user wants to run or understand `GIT_TRACE_PACKET=true git`.
- The user wants to run or understand `GIT_TRACE_PERFORMANCE=true git`.

## When NOT to use

- For git configuration, use the `git-configuration` skill instead.
- For first-time git setup, use the `git-first-time-git-setup` skill instead.
- For credential storage, use the `git-credential-storage` skill instead.

## Key concepts

- A “pathspec” refers to how you specify paths to things in Git, including the use of wildcards.
- The final creation of a Git commit object is usually done by `git-commit-tree`, which uses these environment variables as its primary source of information, falling back to configuration values only if these aren’t present.
- `EMAIL` is the fallback email address in case the `user.email` configuration value isn’t set.
- The default is a value like `git/2.0.0`.
- `GIT_TRACE_SETUP` shows information about what Git is discovering about the repository and environment it’s interacting with.
- `GIT_SSH`, if specified, is a program that is invoked instead of `ssh` when Git tries to connect to an SSH host.
- The default value (if this variable is not set) is to choose an appropriate buffering scheme depending on the activity and the output mode.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- `GIT_FLUSH` can be used to force Git to use non-buffered I/O when writing incrementally to stdout.

## Procedures

### Debugging

**Goal:** `GIT_TRACE_SETUP` shows information about what Git is discovering about the repository and environment it’s interacting with.

**Steps:**

1. This includes the expansion of aliases, and delegation to other sub-programs.
   ```bash
   GIT_TRACE=true git lga
   ```
   Expected output (excerpt):
   ```text
   20:12:49.877982 git.c:554               trace: exec: 'git-lga'
   ```
2. Run:
   ```text
   20:12:49.878369 run-command.c:341       trace: run_command: 'git-lga'
   20:12:49.879529 git.c:282               trace: alias expansion: lga => 'log' '--graph'
   '--pretty=oneline' '--abbrev-commit' '--decorate' '--all'
   20:12:49.879885 git.c:349               trace: built-in: git 'log' '--graph' '--
   pretty=oneline' '--abbrev-commit' '--decorate' '--all'
   20:12:49.899217 run-command.c:341       trace: run_command: 'less'
   20:12:49.899675 run-command.c:192       trace: exec: 'less'
   ```
3. The first field is the packfile being accessed, the second is the offset within that file:
   ```bash
   GIT_TRACE_PACK_ACCESS=true git status
   ```
   Expected output (excerpt):
   ```text
   20:10:12.081397 sha1_file.c:2088        .git/objects/pack/pack-c3fa...291e.pack 12
   20:10:12.081886 sha1_file.c:2088        .git/objects/pack/pack-c3fa...291e.pack 34662
   20:10:12.082115 sha1_file.c:2088        .git/objects/pack/pack-c3fa...291e.pack 35175
   # […]
   ```
4. `GIT_TRACE_PACKET` enables packet-level tracing for network operations.
   ```bash
   GIT_TRACE_PACKET=true git ls-remote origin
   ```
   Expected output (excerpt):
   ```text
   20:15:14.867043 pkt-line.c:46           packet:          git< # service=git-upload-
   pack
   20:15:14.867071 pkt-line.c:46           packet:          git< 0000
   20:15:14.867079 pkt-line.c:46           packet:          git<
   ```
5. The output shows how long each particular `git` invocation takes.
   ```bash
   GIT_TRACE_PERFORMANCE=true git gc
   ```
   Expected output (excerpt):
   ```text
   20:18:19.499676 trace.c:414             performance: 0.374835000 s: git command: 'git'
   'pack-refs' '--all' '--prune'
   ```
6. Run:
   ```text
   20:18:19.845585 trace.c:414             performance: 0.343020000 s: git command: 'git'
   'reflog' 'expire' '--all'
   Counting objects: 170994, done.
   Delta compression using up to 8 threads.
   Compressing objects: 100% (43413/43413), done.
   Writing objects: 100% (170994/170994), done.
   Total 170994 (delta 126176), reused 170524 (delta 125706)
   20:18:23.567927 trace.c:414             performance: 3.715349000 s: git command: 'git'
   'pack-objects' '--keep-true-parents' '--honor-pack-keep' '--non-empty' '--all' '--
   reflog' '--unpack-unreachable=2.weeks.ago' '--local' '--delta-base-offset'
   '.git/objects/pack/.tmp-49190-pack'
   20:18:23.584728 trace.c:414             performance: 0.000910000 s: git command: 'git'
   'prune-packed'
   20:18:23.605218 trace.c:414             performance: 0.017972000 s: git command: 'git'
   'update-server-info'
   # ... (full listing in references)
   ```

_1 more step(s) in references/procedures.md._

### Miscellaneous

**Goal:** The default value (if this variable is not set) is to choose an appropriate buffering scheme depending on the activity and the output mode.

**Steps:**

1. Here’s an example:
   ```bash
   GIT_REFLOG_ACTION="my action" git commit --allow-empty -m 'My message'
   git reflog -1
   ```
   Expected output (excerpt):
   ```text
   [master 9e3d55a] My message
   9e3d55a HEAD@{0}: my action: My message
   ```

More procedures in [references/procedures.md](references/procedures.md):

- Debugging

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `GIT_TRACE=true git` | This includes the expansion of aliases, and delegation to other sub-programs. | `GIT_TRACE=true git lga` |
| `GIT_TRACE_PACK_ACCESS=true git` | The first field is the packfile being accessed, the second is the offset within that file | `GIT_TRACE_PACK_ACCESS=true git status` |
| `GIT_TRACE_PACKET=true git` | `GIT_TRACE_PACKET` enables packet-level tracing for network operations. | `GIT_TRACE_PACKET=true git ls-remote origin` |
| `GIT_TRACE_PERFORMANCE=true git` | The output shows how long each particular `git` invocation takes. | `GIT_TRACE_PERFORMANCE=true git gc` |
| `GIT_TRACE_SETUP=true git` | `GIT_TRACE_SETUP` shows information about what Git is discovering about the repository and environment it’s interacting with. | `GIT_TRACE_SETUP=true git status` |
| `GIT_REFLOG_ACTION="my --allow-empty -m` | Here’s an example | `GIT_REFLOG_ACTION="my action" git commit --allow-empty -m 'My message'` |
| `git reflog` | Here’s an example | `git reflog -1` |

## Decision guide

- If you happen to have a lot of projects with large files that have the exact same contents, this can be used to avoid storing too many copies of them.
- `GIT_SSH`, if specified, is a program that is invoked instead of `ssh` when Git tries to connect to an SSH host.

## Related skills

- `git-configuration` - Git Configuration
- `git-first-time-git-setup` - First-Time Git Setup
- `git-credential-storage` - Credential Storage
- `git-as-a-client` - Git as a Client

## Source

"Pro Git", pages 453-458. Sections: Environment Variables; Environment Variables > Global Behavior; Environment Variables > Repository Locations; Environment Variables > Pathspecs; Environment Variables > Committing; Environment Variables > Networking; Environment Variables > Diffing and Merging; Environment Variables > Debugging; Environment Variables > Miscellaneous.
