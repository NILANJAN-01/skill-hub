#!/usr/bin/env python3
"""Generate a CI pipeline for Playwright tests (GitHub Actions, GitLab CI, Azure Pipelines, Jenkins).

Usage:
    python pw_ci.py --ci github|gitlab|azure|jenkins [--project-dir .] [--shards 4] [--lang node|python]
                    [--env NAME]... [--grep @smoke] [--browsers chromium,firefox] [--out FILE] [--force]

Detects the package manager and the Playwright version from the project to pin the matching Docker
image. Writes secret *references* for each --env name, never values. Standard library only.

Exit codes: 0 ok, 1 output file exists (use --force), 2 bad input.
"""
import argparse
import json
import os
import re
import sys

IMAGE = "mcr.microsoft.com/playwright:v{version}-noble"
IMAGE_PY = "mcr.microsoft.com/playwright/python:v{version}-noble"


# ---------------------------------------------------------------- project detection

def detect(project_dir, lang):
    info = {"pm": "npm", "version": None, "notes": []}
    if lang == "python":
        for name in ("requirements.txt", "requirements-dev.txt", "pyproject.toml"):
            path = os.path.join(project_dir, name)
            if os.path.isfile(path):
                m = re.search(r"""(?<![\w-])playwright\s*(?:==|>=|~=)\s*["']?([0-9]+\.[0-9]+\.[0-9]+)""", _read(path))
                if m:
                    info["version"] = m.group(1)
                    break
        return info
    if os.path.isfile(os.path.join(project_dir, "pnpm-lock.yaml")):
        info["pm"] = "pnpm"
    elif os.path.isfile(os.path.join(project_dir, "yarn.lock")):
        info["pm"] = "yarn"
    lock = os.path.join(project_dir, "package-lock.json")
    if os.path.isfile(lock):
        try:
            data = json.loads(_read(lock))
            pkg = (data.get("packages") or {}).get("node_modules/@playwright/test") or \
                  (data.get("dependencies") or {}).get("@playwright/test") or {}
            info["version"] = pkg.get("version")
        except ValueError:
            pass
    if not info["version"] and os.path.isfile(os.path.join(project_dir, "package.json")):
        try:
            data = json.loads(_read(os.path.join(project_dir, "package.json")))
            spec = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}.get("@playwright/test", "")
            m = re.search(r"([0-9]+\.[0-9]+\.[0-9]+)", spec)
            if m:
                info["version"] = m.group(1)
                if spec[0] in "^~>":
                    info["notes"].append(f"package.json allows a range ({spec}); pin @playwright/test or keep "
                                         "the image tag in step with the installed version")
        except ValueError:
            pass
    return info


def _read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def commands(pm):
    return {"npm": ("npm ci", "npx"), "yarn": ("yarn install --frozen-lockfile", "yarn"),
            "pnpm": ("pnpm install --frozen-lockfile", "pnpm exec")}[pm]


# ---------------------------------------------------------------- generators

def _test_cmd(x, shard, grep, extra=""):
    parts = [f"{x} playwright test"]
    if shard:
        parts.append(f"--shard={shard}")
    if grep:
        parts.append(f'--grep "{grep}"')
        if shard:                       # 1.65+: a sharded run with no matching tests fails without this
            parts.append("--pass-with-no-tests")
    if extra:
        parts.append(extra)
    return " ".join(parts)


def github(o):
    install, x = commands(o["pm"])
    env = "".join(f"\n      {n}: ${{{{ secrets.{n} }}}}" for n in o["env"])
    env_block = f"\n    env:{env}" if env else ""
    if o["lang"] == "python":
        return f"""name: Playwright Tests
on:
  push:
    branches: [main]
  pull_request:
jobs:
  playwright:
    timeout-minutes: 60
    runs-on: ubuntu-latest{env_block}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python -m playwright install --with-deps {o['browsers']}
      - run: pytest --tracing retain-on-failure --output test-results --junitxml=results.xml
      - uses: actions/upload-artifact@v4
        if: ${{{{ !cancelled() }}}}
        with:
          name: playwright-results
          path: |
            results.xml
            test-results/
          retention-days: 14
"""
    n = o["shards"]
    matrix = ", ".join(str(i) for i in range(1, n + 1))
    return f"""name: Playwright Tests
on:
  push:
    branches: [main]
  pull_request:
jobs:
  playwright:
    timeout-minutes: 60
    runs-on: ubuntu-latest{env_block}
    strategy:
      fail-fast: false
      matrix:
        shardIndex: [{matrix}]
        shardTotal: [{n}]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: lts/*
      - run: {install}
      - run: {x} playwright install --with-deps {o['browsers']}
      - run: {_test_cmd(x, '${{ matrix.shardIndex }}/${{ matrix.shardTotal }}', o['grep'], '--reporter=blob')}
      - uses: actions/upload-artifact@v4
        if: ${{{{ !cancelled() }}}}
        with:
          name: blob-report-${{{{ matrix.shardIndex }}}}
          path: blob-report
          retention-days: 1
      - uses: actions/upload-artifact@v4
        if: ${{{{ failure() }}}}
        with:
          name: test-results-${{{{ matrix.shardIndex }}}}
          path: test-results
          retention-days: 7

  merge-reports:
    if: ${{{{ !cancelled() }}}}
    needs: [playwright]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: lts/*
      - run: {install}
      - uses: actions/download-artifact@v4
        with:
          path: all-blob-reports
          pattern: blob-report-*
          merge-multiple: true
      - run: {x} playwright merge-reports --reporter html,junit ./all-blob-reports
        env:
          PLAYWRIGHT_JUNIT_OUTPUT_NAME: results.xml
      - uses: actions/upload-artifact@v4
        with:
          name: playwright-report-attempt-${{{{ github.run_attempt }}}}
          path: |
            playwright-report
            results.xml
          retention-days: 14
"""


def gitlab(o):
    install, x = commands(o["pm"])
    image = (IMAGE_PY if o["lang"] == "python" else IMAGE).format(version=o["version"] or "<PLAYWRIGHT_VERSION>")
    secrets = "".join(f"\n#   {n}" for n in o["env"])
    head = ("# Set these as masked CI/CD variables (Settings > CI/CD > Variables):" + secrets + "\n") if o["env"] else ""
    if o["lang"] == "python":
        return f"""{head}playwright:
  stage: test
  image: {image}
  script:
    - pip install -r requirements.txt
    - pytest --tracing retain-on-failure --output test-results --junitxml=results.xml
  artifacts:
    when: always
    paths: [test-results/]
    reports:
      junit: results.xml
    expire_in: 1 week
"""
    n = o["shards"]
    parallel = f"\n  parallel: {n}" if n > 1 else ""
    shard = "$CI_NODE_INDEX/$CI_NODE_TOTAL" if n > 1 else ""
    return f"""{head}stages: [test, report]

playwright:
  stage: test
  image: {image}{parallel}
  variables:
    npm_config_cache: "$CI_PROJECT_DIR/.npm"
  cache:
    key:
      files: [package-lock.json, yarn.lock, pnpm-lock.yaml]
    paths: [.npm/]
  script:
    - {install}
    - {_test_cmd(x, shard, o['grep'], '--reporter=blob')}
  artifacts:
    when: always
    paths: [blob-report/, test-results/]
    expire_in: 1 week

playwright-report:
  stage: report
  image: {image}
  when: always
  needs: [playwright]
  script:
    - {install}
    - PLAYWRIGHT_JUNIT_OUTPUT_NAME=results.xml {x} playwright merge-reports --reporter html,junit ./blob-report
  artifacts:
    when: always
    paths: [playwright-report/]
    reports:
      junit: results.xml
    expire_in: 2 weeks
"""


def azure(o):
    install, x = commands(o["pm"])
    env = "".join(f"\n      {n}: $({n})" for n in o["env"])
    if o["lang"] == "python":
        return f"""trigger: [main]
pool:
  vmImage: ubuntu-latest
jobs:
  - job: playwright
    timeoutInMinutes: 60
    steps:
      - task: UsePythonVersion@0
        inputs:
          versionSpec: '3.12'
      - script: pip install -r requirements.txt
      - script: python -m playwright install --with-deps {o['browsers']}
      - script: pytest --tracing retain-on-failure --output test-results --junitxml=results.xml
        displayName: Run Playwright tests{('''
        env:''' + env) if env else ''}
      - task: PublishTestResults@2
        condition: succeededOrFailed()
        inputs:
          testResultsFormat: JUnit
          testResultsFiles: results.xml
      - publish: test-results
        artifact: test-results-$(System.JobAttempt)
        condition: failed()
"""
    n = o["shards"]
    strategy = f"\n    strategy:\n      parallel: {n}" if n > 1 else ""
    shard = "$(System.JobPositionInPhase)/$(System.TotalJobsInPhase)" if n > 1 else ""
    return f"""trigger: [main]
pool:
  vmImage: ubuntu-latest
jobs:
  - job: playwright
    timeoutInMinutes: 60{strategy}
    steps:
      - task: NodeTool@0
        inputs:
          versionSpec: '22.x'
      - script: {install}
      - script: {x} playwright install --with-deps {o['browsers']}
      - script: {_test_cmd(x, shard, o['grep'], '--reporter=junit,html')}
        displayName: Run Playwright tests
        env:
          PLAYWRIGHT_JUNIT_OUTPUT_NAME: results.xml{env}
      - task: PublishTestResults@2
        condition: succeededOrFailed()
        inputs:
          testResultsFormat: JUnit
          testResultsFiles: results.xml
          testRunTitle: Playwright $(System.JobPositionInPhase)
      - publish: playwright-report
        artifact: playwright-report-$(System.JobPositionInPhase)-$(System.JobAttempt)
        condition: succeededOrFailed()
      - publish: test-results
        artifact: test-results-$(System.JobPositionInPhase)-$(System.JobAttempt)
        condition: failed()
"""


def jenkins(o):
    install, x = commands(o["pm"])
    image = (IMAGE_PY if o["lang"] == "python" else IMAGE).format(version=o["version"] or "<PLAYWRIGHT_VERSION>")
    env = "".join(f"\n    {n} = credentials('{n}')" for n in o["env"])
    env_block = f"\n  environment {{{env}\n  }}" if env else ""
    if o["lang"] == "python":
        stages = """    stage('Install') { steps { sh 'pip install -r requirements.txt' } }
    stage('Test') { steps { sh 'pytest --tracing retain-on-failure --output test-results --junitxml=results-1.xml' } }"""
    else:
        n = o["shards"]
        shard_stages = "\n".join(
            f"        stage('Shard {i}') {{ steps {{ sh 'PLAYWRIGHT_JUNIT_OUTPUT_NAME=results-{i}.xml "
            f"{_test_cmd(x, f'{i}/{n}' if n > 1 else '', o['grep'].replace(chr(39), '') if o['grep'] else '', f'--reporter=junit --output=test-results-{i}')}' }} }}"
            for i in range(1, n + 1))
        stages = f"""    stage('Install') {{ steps {{ sh '{install}' }} }}
    stage('Test') {{
      parallel {{
{shard_stages}
      }}
    }}"""
    return f"""pipeline {{
  agent {{
    docker {{
      image '{image}'
      args '--ipc=host'
    }}
  }}
  options {{ timeout(time: 60, unit: 'MINUTES') }}{env_block}
  stages {{
{stages}
  }}
  post {{
    always {{
      junit allowEmptyResults: true, testResults: '**/results-*.xml'
      archiveArtifacts artifacts: 'test-results*/**', allowEmptyArchive: true
    }}
  }}
}}
"""


GENERATORS = {"github": github, "gitlab": gitlab, "azure": azure, "jenkins": jenkins}
DEFAULT_OUT = {"github": ".github/workflows/playwright.yml", "gitlab": ".gitlab-ci.yml",
               "azure": "azure-pipelines.yml", "jenkins": "Jenkinsfile"}


def generate(ci, project_dir=".", shards=1, lang="node", env=None, grep=None, browsers=None):
    if ci not in GENERATORS:
        raise ValueError(f"unknown CI {ci!r}; choose {', '.join(GENERATORS)}")
    if shards < 1 or shards > 64:
        raise ValueError("--shards must be 1..64")
    for name in env or []:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise ValueError(f"bad variable name {name!r}")
    info = detect(project_dir, lang)
    notes = list(info["notes"])
    if lang == "python":
        if shards > 1:
            notes.append("pytest-playwright has no built-in sharding: generated one job; use pytest-xdist (-n auto) "
                         "to run tests in parallel inside it")
            shards = 1
        if grep:
            notes.append("--grep is for Playwright Test; with pytest use -k or -m in the pytest command")
            grep = None
    if ci in ("gitlab", "jenkins") and not info["version"]:
        notes.append("Playwright version not found: replace <PLAYWRIGHT_VERSION> in the image tag with the "
                     "version of @playwright/test (or playwright for Python)")
    o = {"pm": info["pm"], "version": info["version"], "shards": shards, "lang": lang, "env": list(env or []),
         "grep": grep, "browsers": " ".join(b.strip() for b in (browsers or "").split(",") if b.strip())}
    text = GENERATORS[ci](o)
    return text.replace(" \n", "\n"), notes, info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ci", required=True, choices=sorted(GENERATORS))
    ap.add_argument("--project-dir", default=".", help="project root (to detect package manager and version)")
    ap.add_argument("--shards", type=int, default=1, help="number of parallel shards (default 1)")
    ap.add_argument("--lang", choices=["node", "python"], default="node")
    ap.add_argument("--env", action="append", default=[], metavar="NAME", help="secret/variable the tests need (repeatable)")
    ap.add_argument("--grep", help="only run tests matching this tag/title, e.g. @smoke")
    ap.add_argument("--browsers", help="comma list of browsers to install (default: all)")
    ap.add_argument("--out", help=f"write here (e.g. {', '.join(DEFAULT_OUT.values())}); default: print")
    ap.add_argument("--force", action="store_true", help="overwrite --out if it exists")
    opts = ap.parse_args(argv)
    try:
        text, notes, info = generate(opts.ci, opts.project_dir, opts.shards, opts.lang, opts.env, opts.grep, opts.browsers)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if opts.out:
        if os.path.exists(opts.out) and not opts.force:
            print(f"{opts.out} exists; merge the output by hand or pass --force", file=sys.stderr)
            return 1
        os.makedirs(os.path.dirname(os.path.abspath(opts.out)), exist_ok=True)
        with open(opts.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"wrote {opts.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    print(f"# package manager: {info['pm']}, Playwright version: {info['version'] or 'unknown'}", file=sys.stderr)
    for note in notes:
        print(f"# note: {note}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
