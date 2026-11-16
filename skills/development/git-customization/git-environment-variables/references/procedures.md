# More procedures: Environment Variables

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
   20:18:23.606342 trace.c:414             performance: 3.756312000 s: git command: 'git'
   'repack' '-d' '-l' '-A' '--unpack-unreachable=2.weeks.ago'
   Checking connectivity: 170994, done.
   20:18:25.225424 trace.c:414             performance: 1.616423000 s: git command: 'git'
   'prune' '--expire' '2.weeks.ago'
   20:18:25.232403 trace.c:414             performance: 0.001051000 s: git command: 'git'
   'rerere' 'gc'
   20:18:25.233159 trace.c:414             performance: 6.112217000 s: git command: 'git'
   'gc'
   ```
7. `GIT_TRACE_SETUP` shows information about what Git is discovering about the repository and environment it’s interacting with.
   ```bash
   GIT_TRACE_SETUP=true git status
   ```
   Expected output (excerpt):
   ```text
   20:19:47.086765 trace.c:315             setup: git_dir: .git
   20:19:47.087184 trace.c:316             setup: worktree: /Users/ben/src/git
   20:19:47.087191 trace.c:317             setup: cwd: /Users/ben/src/git
   20:19:47.087194 trace.c:318             setup: prefix: (null)
   ```
