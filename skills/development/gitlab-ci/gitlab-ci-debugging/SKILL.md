---
name: gitlab-ci-debugging
description: "Diagnose a failing, stuck, skipped or wrongly triggered GitLab CI pipeline or job from its log and .gitlab-ci.yml. Use when the user says a GitLab pipeline is stuck, pending, not running, created no jobs, or a job fails (exit code, runner, rules, artifacts, Docker)."
license: Complete terms in the repository README
metadata:
  title: "GitLab CI debugging"
  category: gitlab-ci-tools
---

# GitLab CI debugging

Find the cause of a pipeline problem from the log and config, then give the smallest fix.

## When to use

- A job failed and the user shares its log, or the pipeline page shows an error.
- A pipeline is "stuck", "pending", "skipped", or shows "No stages / jobs for this pipeline".
- A job runs when it shouldn't, or doesn't run when it should.
- Artifacts, cache, variables or services behave unexpectedly.

## When NOT to use

- Writing a new pipeline: `gitlab-ci-pipeline-authoring`. Making it faster: `gitlab-ci-optimization`.

## Safety rules for the agent

- Logs can contain secrets. Don't repeat tokens or passwords back; tell the user to rotate any that leaked.
- Don't change project CI/CD variables or runners, or retry production deploy jobs, without the user's approval.

## Procedure

1. Get the evidence: the failing job's log (the first error, not the last line), the `.gitlab-ci.yml`, and whether it is a merge request, branch or tag pipeline.
2. Classify the failure:
   - **Pipeline not created**: a YAML or `workflow:rules` problem. Run CI Lint and read the exact message.
   - **Job not created or skipped**: `rules` matched nothing. Check the pipeline source (`$CI_PIPELINE_SOURCE`), branch vs merge request, and `changes:` (it needs a diff base).
   - **Pending or stuck**: no runner with matching `tags`, runner offline or paused, a protected-only runner on an unprotected ref, or the runner quota is used up.
   - **Script failed**: find the first non-zero command. Reproduce locally with the same image (`docker run -it <image> sh`).
   - **Infrastructure**: image pull errors, Docker-in-Docker setup, runner out of disk or memory (exit 137 means killed for memory).
3. Check data flow: `needs` and `dependencies` decide which artifacts a job downloads; `artifacts:paths` must match files that exist after the script; cache keys must match across jobs that share a cache.
4. Print variables safely: `env | sort | grep '^CI_'`. Protected and masked variables only exist on matching refs.
5. Propose the minimal YAML or settings fix and say how to confirm it (re-run the job, or CI Lint).

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `This job is stuck because the project doesn't have any runners online assigned to it` | Enable a shared runner, start the project runner, or remove unmatched `tags:` |
| `Pipeline will not run for the selected trigger` | Every `workflow:rules` entry failed to match |
| `'job' job needs 'x' job, but 'x' is not in any previous stage` | `needs` points to a job filtered out by `rules`; add `optional: true` or fix the rules |
| `ERROR: Job failed: exit code 137` | Out of memory; use a bigger runner or reduce parallelism |
| `Cannot connect to the Docker daemon` | Add the `docker:dind` service and set `DOCKER_HOST` and `DOCKER_TLS_CERTDIR` |
| `fatal: could not read Username` | Private dependency or submodule; use `CI_JOB_TOKEN` and allow it in project settings |
| Artifacts missing in a later job | Default is `when: on_success`; add `when: always`, check `expire_in` and `dependencies:` |
| Cache never hits | Different `cache:key` per job or branch, or runners don't share a cache |
