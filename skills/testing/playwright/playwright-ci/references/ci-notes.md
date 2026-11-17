# CI notes

Official guide: https://playwright.dev/docs/ci and https://playwright.dev/docs/test-sharding

## GitHub Actions

- Shards as a matrix (`shardIndex: [1..n]`, `fail-fast: false`), each uploading `blob-report` as `blob-report-<i>`; a `merge-reports` job downloads them with `pattern: blob-report-*` and `merge-multiple: true`.
- Use `if: ${{ !cancelled() }}` on uploads so failed runs still publish.
- Secrets: `env: { E2E_PASSWORD: ${{ secrets.E2E_PASSWORD }} }`; non-secret settings in `vars`.
- Cache: `actions/setup-node` with `cache: npm`; caching browsers rarely pays off (download is fast, cache restore is similar).

## GitLab CI

- `parallel: n` gives `CI_NODE_INDEX` / `CI_NODE_TOTAL` for `--shard`.
- Use the Playwright image so no browser install is needed; artifacts from all parallel jobs are merged into the report job through `needs:`.
- `artifacts:reports:junit` shows results in merge requests.
- Variables: mark credentials as masked and protected.

## Azure Pipelines

- `strategy: parallel: n` with `$(System.JobPositionInPhase)/$(System.TotalJobsInPhase)` for `--shard`.
- Secret variables are not exposed to scripts automatically: map them under the step's `env:`.
- `PublishTestResults@2` with `condition: succeededOrFailed()` puts JUnit results in the Tests tab.

## Jenkins

- Declarative pipeline with a Docker agent on the Playwright image and `--ipc=host`.
- Parallel stages share one workspace: give each shard its own `--output` folder and JUnit file name.
- Credentials via `environment { NAME = credentials('id') }`.

## Smoke vs full suite

- Pull requests: `--grep @smoke`, 1–2 shards, chromium only.
- Main branch / nightly: full suite, all browser projects, more shards.
- Generate both with `pw_ci.py` (one with `--grep @smoke`) or add a variable that switches `--grep`.

## Choosing shard count

Measure one full run (`pw_report.py` shows total test time). Shards ≈ total test minutes ÷ (target wall-clock minutes × workers per shard). Add a few minutes per shard for setup (checkout, install).
