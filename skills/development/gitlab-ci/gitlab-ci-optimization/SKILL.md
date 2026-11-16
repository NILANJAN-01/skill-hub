---
name: gitlab-ci-optimization
description: "Make a GitLab CI pipeline faster and cheaper: needs (DAG), cache, parallel jobs, rules:changes, interruptible, smaller images, Docker layer caching. Use when the user says a GitLab pipeline is slow or wastes CI minutes."
license: Complete terms in the repository README
metadata:
  title: "GitLab CI optimization"
  category: gitlab-ci-tools
---

# GitLab CI optimization

Measure first, then change the few things that dominate pipeline time.

## When to use

- Pipelines take too long or queue for runners.
- The user wants to cut CI minutes or avoid running unneeded jobs.

## When NOT to use

- The pipeline is broken (use `gitlab-ci-debugging`) or doesn't exist yet (use `gitlab-ci-pipeline-authoring`).

## Safety rules for the agent

- Don't remove tests or security scans to save time without the user's agreement.
- Change one thing at a time so the effect can be measured and reverted.

## Procedure

1. Measure: find the critical path (the longest chain of jobs) and each job's duration, including image pull, checkout and dependency install. Ask for the pipeline graph or job timings if not given.
2. Apply, in this usual order of payoff:
   - **DAG with `needs:`**: jobs start when their inputs finish, not when the stage ends.
   - **Skip unneeded work**: `rules: - changes: [...]` for jobs tied to certain paths; avoid duplicate branch and merge request pipelines with `workflow:rules`.
   - **Cancel stale runs**: `interruptible: true` on test jobs, and enable auto-cancel of redundant pipelines.
   - **Cache dependencies**, keyed on the lockfile:
     ```yaml
     cache:
       key:
         files: [package-lock.json]
       paths: [.npm/]
       policy: pull   # only the install job uses pull-push
     ```
   - **Parallelize**: `parallel: 4` or `parallel: matrix:`, splitting tests with `CI_NODE_INDEX` and `CI_NODE_TOTAL`.
   - **Smaller inputs**: slim image tags, `GIT_DEPTH: 20`, `GIT_STRATEGY: none` for jobs that need no source, artifacts limited to needed paths with `expire_in`.
   - **Docker builds**: reuse layers (BuildKit with a registry cache), and order Dockerfile steps from least to most changing.
3. Re-run and compare with the baseline. Keep a change only if it helped.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Cache restore and save take longer than the install | Cache less, use `policy: pull`, or use a distributed cache |
| A `needs` job ran without the artifact it needs | Keep `artifacts: true` and make sure the producing job lists the paths |
| Parallel jobs finish unevenly | Split by timing data, not by file count |
| Jobs wait for a runner | Add runners, raise the runner `concurrent` limit, or reduce parallelism |
