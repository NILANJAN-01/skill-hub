# Enforcing the guardrails in hooks and CI

The block in the instruction files tells agents what to do; the hook and CI make sure it happened. All commands assume the checker was copied to `tools/design_check.py` by `install_guardrails.py install` (change the path if you used `--vendor`).

## Adopting on an existing code base

Old code usually has many findings. Do not fix them in one sweep. Record them once and only block new ones:

```bash
python tools/design_check.py --write-baseline .design-baseline.json
git add .design-baseline.json
python tools/design_check.py --baseline .design-baseline.json      # only findings not in the baseline
```

Fingerprints use the rule, the file and the function name or line text, not line numbers, so unrelated edits do not resurrect old findings. Regenerate the baseline when a cleanup removes findings. Diff mode (`--diff`, `--staged`) needs no baseline, because it only reports changed lines.

## Pre-commit hook

`install_guardrails.py install --hook --yes` writes `.git/hooks/pre-commit`, which runs:

```bash
python tools/design_check.py --staged --fail-on warning
```

Hooks are local to each clone. CI is what enforces the rules for everyone.

### With the pre-commit framework

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: design-check
        name: software design red flags
        entry: python tools/design_check.py --staged --fail-on warning
        language: system
        pass_filenames: false
```

## GitHub Actions

```yaml
# .github/workflows/design-check.yml
name: design-check
on: [pull_request]
jobs:
  design-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python tools/design_check.py --diff origin/${{ github.base_ref }} --fail-on warning
```

## GitLab CI

```yaml
design-check:
  image: python:3.12-slim
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  before_script:
    - apt-get update -qq && apt-get install -y -qq git
    - git fetch origin $CI_MERGE_REQUEST_TARGET_BRANCH_NAME
  script:
    - python tools/design_check.py --diff origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME --fail-on warning
```

## Reports

`--format json` prints every finding with rule, severity, red flag, chapter, path, line, message and fix, plus a summary. Use it to post review comments or to track counts over time.

## Choosing the threshold

| Setting | Effect |
|---|---|
| `--fail-on warning` (default) | Blocks pass-throughs, long parameter lists, swallowed errors and duplicated code |
| `--fail-on info` | Also blocks naming, comment and interface-doc findings. Use on new projects |
| `--fail-on never` | Report only. Use while a team gets used to the rules |
