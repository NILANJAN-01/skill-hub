---
name: gitlab-ci-pipeline-authoring
description: "Write or change a GitLab CI pipeline (.gitlab-ci.yml): stages, jobs, rules, needs, artifacts, cache, includes and merge request pipelines. Use when the user asks to create or extend a GitLab pipeline or job, or run a job only on certain branches, tags or changes."
license: Complete terms in the repository README
metadata:
  title: "GitLab CI pipeline authoring"
  category: gitlab-ci-tools
---

# GitLab CI pipeline authoring

Helps write a correct, readable `.gitlab-ci.yml` from the project's real build and test commands.

## When to use

- Create a new pipeline, or add a build, test, lint, package or deploy job.
- Run jobs only for merge requests, the default branch, tags or changed files.
- Split a long file with `include`, `extends`, hidden jobs, `!reference` or child pipelines.
- Pass files between jobs (artifacts), or reuse downloads (cache).

## When NOT to use

- A pipeline already exists and fails: use `gitlab-ci-debugging`.
- A working pipeline is too slow or costly: use `gitlab-ci-optimization`.

## Safety rules for the agent

- Never put secrets in the YAML. Use masked, protected CI/CD variables set in project settings, and reference them as `$NAME`.
- Production deploy jobs should be `when: manual` or limited to protected branches/tags. Confirm with the user first.
- Don't invent build commands. Read the project (package manifest, Makefile, README) to find them, or ask.

## Procedure

1. Find how the project builds, tests and deploys, and which runtime image fits (pin a version tag, not `latest`).
2. Sketch stages (usually `build`, `test`, `deploy`) and which jobs go in each.
3. Write the file, starting from this skeleton:
   ```yaml
   stages: [build, test, deploy]

   workflow:
     rules:
       - if: $CI_PIPELINE_SOURCE == "merge_request_event"
       - if: $CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS
         when: never            # avoid duplicate branch + MR pipelines
       - if: $CI_COMMIT_BRANCH
       - if: $CI_COMMIT_TAG

   default:
     image: node:20
     interruptible: true

   build:
     stage: build
     script: [npm ci, npm run build]
     artifacts:
       paths: [dist/]
       expire_in: 1 week

   test:
     stage: test
     needs: [build]
     script: [npm test]

   deploy:
     stage: deploy
     script: [./deploy.sh]
     environment: production
     rules:
       - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
         when: manual
   ```
4. Use `rules:` (not the old `only/except`). Common conditions:
   - merge request: `$CI_PIPELINE_SOURCE == "merge_request_event"`
   - default branch: `$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH`
   - tag: `$CI_COMMIT_TAG`
   - changed files: `changes: [src/**/*]`
5. Share configuration instead of copying it: hidden jobs (`.base:`) with `extends:`, `include: local/project/template/remote`, and `!reference [.base, script]`.
6. Use `needs:` to start jobs as soon as their inputs are ready, not when the whole stage ends.
7. Validate before pushing: use the CI Lint page, the lint API (`POST /api/v4/projects/:id/ci/lint`), or the pipeline editor.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `jobs:x config should implement the script:, run:, or trigger: keyword` | A key sits at top level that isn't a job, or `script` is missing. Prefix non-jobs with `.` or move settings under `default:` |
| `chosen stage does not exist` | The job's `stage` isn't listed in `stages:` |
| Two pipelines per push | Add the `workflow:rules` block above |
| Secret printed in the log | Mark the variable masked; never `echo` it |
