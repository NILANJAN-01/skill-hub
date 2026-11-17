---
name: playwright-ci
description: "Run Playwright tests in CI: GitHub Actions, GitLab CI, Azure Pipelines or Jenkins, with sharding, merged HTML reports, JUnit results, traces as artifacts, the matching Docker image and secrets. A script generates the pipeline file from the project. Use when the user wants Playwright in CI, faster runs with shards, or CI reports and artifacts."
license: MIT
compatibility: The generator needs Python 3.8+ (standard library only). Pipelines run Node.js with @playwright/test, or Python with pytest-playwright.
metadata:
  title: "Playwright in CI: pipelines, sharding and reports"
  category: playwright-tools
---

# Playwright in CI

Get a Playwright suite running in the company's CI system with fast, readable results: browsers installed (or the official Docker image), tests split across shards, one merged report, JUnit results in the CI UI, and traces kept for failures.

## When to use

- Add Playwright to GitHub Actions, GitLab CI, Azure Pipelines or Jenkins.
- The suite is too slow in CI and needs sharding.
- CI shows no report, no traces, or results are hard to read.

## When NOT to use

- Tests fail and you need the cause: use `playwright-debugging`.
- Writing the tests themselves: use `playwright-test-authoring`.
- General GitLab pipeline design beyond Playwright: use `gitlab-ci-pipeline-authoring`.

## Procedure

1. **Check the project.** Find the package manager (lockfile), the `@playwright/test` (or `playwright` for Python) version, the config's `reporter`, `retries`, `trace` and `baseURL`, and which secrets the tests need (`BASE_URL`, test account credentials). The test-authoring skill's `pw_audit.py` reports the config.
2. **Generate the pipeline** (prints to the screen unless `--out` is given; never overwrites without `--force`):
   ```bash
   python scripts/pw_ci.py --ci github --project-dir . --shards 4 --env BASE_URL --env E2E_USER --env E2E_PASSWORD
   python scripts/pw_ci.py --ci gitlab --shards 3 --grep @smoke --out .gitlab-ci.playwright.yml
   python scripts/pw_ci.py --ci azure --shards 2
   python scripts/pw_ci.py --ci jenkins --shards 2 --out Jenkinsfile
   python scripts/pw_ci.py --ci github --lang python            # pytest-playwright
   ```
   It detects npm / yarn / pnpm from the lockfile and the Playwright version (to pin the matching `mcr.microsoft.com/playwright:v<version>-noble` image), shards with `--shard=i/n`, writes blob reports per shard and merges them into one HTML report (plus JUnit for the CI's test tab), uploads traces from `test-results/` when tests fail, and maps each `--env` name to the CI's secret mechanism. `--browsers chromium,firefox` limits browser installation; `--grep` selects tagged tests.
3. **Store the secrets** in the CI (GitHub: repository secrets/variables; GitLab: masked CI/CD variables; Azure: secret pipeline variables; Jenkins: credentials). Never commit them.
4. **Review the generated file**, merge it into the existing pipeline (GitLab: `include:` it or copy the jobs; GitHub: a new workflow file), and run it on a branch.
5. **Tune:** number of shards ≈ suite minutes ÷ target minutes per shard; keep `retries: 2` on CI; `workers` 1–2 per shard on small runners; split a fast `@smoke` job for pull requests and the full suite nightly. Newer options worth setting (1.61–1.65):
   - `retryStrategy: 'isolated'` runs retries at the end, one at a time, so a test that only fails under load shows up as flaky clearly.
   - `failOnFlakyTests: true` (or `--fail-on-flaky-tests`) on the main branch if the team treats flakiness as a failure.
   - `reporter: [['failures'], ['blob']]`: the `failures` reporter prints only failures and retries, keeping CI logs short; `onlyFailures: true` on `html`/`json`/`junit` shrinks reports.
   - `--add-reporter` adds a reporter without replacing the config's; `testConfig.tag` labels every test of a run (e.g. the environment) in merged reports.
6. **Read results:** download the merged `playwright-report` artifact (`npx playwright show-report <folder>`), or feed its JSON/JUnit to `playwright-debugging`'s `pw_report.py`.

## Key facts

| Topic | Detail |
|---|---|
| Browsers | `npx playwright install --with-deps [browser...]` on plain runners; the Docker image `mcr.microsoft.com/playwright:v<same version as @playwright/test>-noble` already has them. Mismatched versions fail with "Executable doesn't exist" |
| Sharding | `npx playwright test --shard=1/4`; each shard writes a blob report (`--reporter=blob`, unique file names); `npx playwright merge-reports --reporter html ./all-blob-reports` joins them. Since 1.65 a sharded run whose filter matches no tests at all fails: the generator adds `--pass-with-no-tests` when `--grep` is used |
| Runtimes | Playwright 1.65 needs Node.js 22+ (Node 20 dropped; 16 and 18 earlier); the official Docker images ship Node 24. Ubuntu 20.04 and Debian 11 are no longer supported hosts |
| Reports | `PLAYWRIGHT_JUNIT_OUTPUT_NAME=results.xml` with the `junit` reporter for CI test tabs; `PLAYWRIGHT_JSON_OUTPUT_NAME` for JSON |
| Docker | Run as the image's user, add `--ipc=host` for Chromium, and keep the image tag in step with the package version |
| Python | `pip install pytest-playwright`, `python -m playwright install --with-deps`, `pytest --tracing retain-on-failure --junitxml=results.xml`; split runs with pytest-xdist (`-n auto`) |

## Safety rules

- Secrets only through the CI's secret store; the generator writes references, never values.
- Point CI at a test environment, never production, unless the suite is read-only and agreed.
- Artifacts (traces, videos, reports) can contain session data: keep retention short and access internal.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Executable doesn't exist at .../ms-playwright/...` | Browsers not installed or image version differs from `@playwright/test`: run `playwright install --with-deps` or fix the image tag |
| `Host system is missing dependencies` | Use `--with-deps` or the official image |
| Merged report is empty | Blob reports were not collected: check artifact names/paths and that every shard uploads with "always" |
| `No tests found` on a sharded `--grep` run (1.65+) | No test matches the filter in any shard: add `--pass-with-no-tests`, or fix the tag |
| Node.js version error after upgrading | Playwright 1.65 needs Node 22+: update `node-version` / `NodeTool` / the base image |
| Shards very uneven | Turn on `fullyParallel: true` so tests (not files) are split |
| Tests time out only in CI | Fewer CPUs: lower `workers`, raise `expect` timeout slightly, check the app server's speed |

## References

- [references/ci-notes.md](references/ci-notes.md): per-CI notes, caching, and splitting smoke vs full runs.
