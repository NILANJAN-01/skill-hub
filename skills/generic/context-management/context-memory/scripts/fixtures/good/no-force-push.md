---
name: no-force-push
description: never force-push shared branches; ask first
metadata:
  type: feedback
---

Never run a force push on `main` or any branch others use; ask the user first.

**Why:** a force push on 2026-10-02 erased a teammate's commits.

**How to apply:** for rewritten history, push a new branch instead. See [[branch-naming]].
