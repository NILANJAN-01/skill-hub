#!/usr/bin/env python3
"""Generate a CI pipeline for Robot Framework (GitHub Actions, GitLab CI, Azure Pipelines, Jenkins).

Usage:
    python rf_ci.py --ci github|gitlab|azure|jenkins [--project-dir .] [--tests tests]
                    [--pabot N] [--no-rerun] [--include TAG] [--variablefile FILE]
                    [--env NAME]... [--browser-lib] [--out FILE] [--force]

The run step executes the suite (robot, or pabot with N processes), reruns only failed tests once,
merges the results with rebot so tests that passed on rerun count as passed (and show as re-executed),
writes xunit.xml for the CI's test view, and keeps results/ as an artifact. Secrets are referenced,
never written. Standard library only.

Exit codes: 0 ok, 1 output file exists (use --force), 2 bad input.
"""
import argparse
import os
import re
import sys

PY = "3.13"


def detect(project_dir):
    info = {"rf": None, "browser": None, "pabot": False, "requirements": None}
    for name in ("requirements.txt", "requirements-dev.txt", "requirements/test.txt", "pyproject.toml"):
        path = os.path.join(project_dir, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            text = fh.read()
        info["requirements"] = info["requirements"] or (name if name.endswith(".txt") else None)
        m = re.search(r"""(?<![\w-])robotframework\s*["']?\s*(?:==|>=|~=)\s*["']?([0-9.]+)""", text, re.I)
        info["rf"] = info["rf"] or (m.group(1) if m else None)
        m = re.search(r"""robotframework-browser\s*["']?\s*(?:==|>=|~=)\s*["']?([0-9.]+)""", text, re.I)
        info["browser"] = info["browser"] or (m.group(1) if m else ("any" if "robotframework-browser" in text else None))
        info["pabot"] = info["pabot"] or "robotframework-pabot" in text
    return info


def run_block(o, indent):
    first = f"pabot --processes {o['pabot']}" if o["pabot"] else "robot"
    args = []
    if o["include"]:
        args.append(f'--include "{o["include"]}"')
    if o["variablefile"]:
        args.append(f"--variablefile {o['variablefile']}")
    a = (" " + " ".join(args)) if args else ""
    t = o["tests"]
    if not o["rerun"]:
        lines = [f"{first} --outputdir results --xunit xunit.xml{a} {t}"]
    else:
        lines = [
            "# Run, rerun only failed tests once, merge: tests that pass on rerun count as passed.",
            "set +e    # CI shells use -e; the first run's exit code (= failed tests) must not stop the step",
            f"{first} --outputdir results --xunit xunit.xml{a} {t}",
            "rc=$?",
            'if [ "$rc" -ge 1 ] && [ "$rc" -le 250 ]; then',
            f"  robot --outputdir results --rerunfailed results/output.xml --output rerun.xml{a} {t}",
            "  rebot --outputdir results --output merged.xml --xunit xunit.xml --merge results/output.xml results/rerun.xml",
            "  rc=$?",
            "fi",
            "exit $rc",
        ]
    pad = " " * indent
    return "\n".join(pad + line for line in lines)


def install_lines(o, venv=False):
    req = o["requirements"] or "requirements.txt"
    lines = [f"pip install -r {req}"]
    if o["pabot"] and not o["has_pabot"]:
        lines[0] += " robotframework-pabot"
    if o["browser"]:
        lines.append("rfbrowser init")
    return lines


def github(o):
    env = "\n      PYTHONIOENCODING: utf-8" + "".join(f"\n      {n}: ${{{{ secrets.{n} }}}}" for n in o["env"])
    node = """
      - uses: actions/setup-node@v4
        with:
          node-version: lts/*""" if o["browser"] else ""
    installs = "".join(f"\n      - run: {line}" for line in install_lines(o))
    return f"""name: Robot Framework
on:
  push:
    branches: [main]
  pull_request:
jobs:
  robot:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    env:{env}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '{PY}'
          cache: pip{node}{installs}
      - name: Run Robot Framework
        shell: bash
        run: |
{run_block(o, 10)}
      - uses: actions/upload-artifact@v4
        if: ${{{{ !cancelled() }}}}
        with:
          name: robot-results-${{{{ github.run_attempt }}}}
          path: results/
          retention-days: 14
"""


def _image(o):
    if o["browser"]:
        tag = o["browser"] if o["browser"] not in (None, "any") else "<ROBOTFRAMEWORK_BROWSER_VERSION>"
        return f"marketsquare/robotframework-browser:{tag}", True
    return f"python:{PY}", False


def gitlab(o):
    image, browser_image = _image(o)
    secrets = "".join(f"\n#   {n}" for n in o["env"])
    head = ("# Set these as masked CI/CD variables (Settings > CI/CD > Variables); tests read them with %{NAME}:"
            + secrets + "\n") if o["env"] else ""
    note = ("# Browser library: official image with Node.js and browsers; check the tag matches robotframework-browser.\n"
            if browser_image else "")
    installs = [l for l in install_lines(o) if not (browser_image and l == "rfbrowser init")]
    before = "".join(f"\n    - {l}" for l in installs)
    return f"""{head}{note}robot:
  image: {image}
  variables:
    PYTHONIOENCODING: utf-8
    PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
  cache:
    paths: [.cache/pip]
  before_script:{before}
  script:
    - |
{run_block(o, 6)}
  artifacts:
    when: always
    paths: [results/]
    reports:
      junit: results/xunit.xml
    expire_in: 2 weeks
"""


def azure(o):
    env = "\n      PYTHONIOENCODING: utf-8" + "".join(f"\n      {n}: $({n})" for n in o["env"])
    node = """
      - task: NodeTool@0
        inputs:
          versionSpec: '22.x'""" if o["browser"] else ""
    installs = "".join(f"\n      - script: {l}" for l in install_lines(o))
    return f"""trigger: [main]
pool:
  vmImage: ubuntu-latest
jobs:
  - job: robot
    timeoutInMinutes: 60
    steps:
      - task: UsePythonVersion@0
        inputs:
          versionSpec: '{PY}'{node}{installs}
      - bash: |
{run_block(o, 10)}
        displayName: Run Robot Framework
        env:{env}
      - task: PublishTestResults@2
        condition: succeededOrFailed()
        inputs:
          testResultsFormat: JUnit
          testResultsFiles: results/xunit.xml
          testRunTitle: Robot Framework
      - publish: results
        artifact: robot-results-$(System.JobAttempt)
        condition: succeededOrFailed()
"""


def jenkins(o):
    image, browser_image = _image(o)
    env = "\n    PYTHONIOENCODING = 'utf-8'" + "".join(f"\n    {n} = credentials('{n}')" for n in o["env"])
    installs = [l for l in install_lines(o) if not (browser_image and l == "rfbrowser init")]
    install = " && ".join(["python -m venv .venv", ". .venv/bin/activate"] + installs)
    block = run_block(o, 10).replace("exit $rc", "exit $rc")
    return f"""pipeline {{
  agent {{ docker {{ image '{image}' }} }}
  options {{ timeout(time: 60, unit: 'MINUTES') }}
  environment {{{env}
  }}
  stages {{
    stage('Install') {{
      steps {{ sh '{install}' }}
    }}
    stage('Robot Framework') {{
      steps {{
        sh '''#!/bin/bash
          . .venv/bin/activate
{block}
        '''
      }}
    }}
  }}
  post {{
    always {{
      junit allowEmptyResults: true, testResults: 'results/xunit.xml'
      archiveArtifacts artifacts: 'results/**', allowEmptyArchive: true
      // With the Robot Framework Jenkins plugin: robot outputPath: 'results'
    }}
  }}
}}
"""


GENERATORS = {"github": github, "gitlab": gitlab, "azure": azure, "jenkins": jenkins}
DEFAULT_OUT = {"github": ".github/workflows/robot.yml", "gitlab": ".gitlab-ci.yml", "azure": "azure-pipelines.yml",
               "jenkins": "Jenkinsfile"}


def generate(ci, project_dir=".", tests="tests", pabot=0, rerun=True, include=None, variablefile=None, env=None,
             browser_lib=False):
    if ci not in GENERATORS:
        raise ValueError(f"unknown CI {ci!r}; choose {', '.join(GENERATORS)}")
    if pabot < 0 or pabot > 64:
        raise ValueError("--pabot must be 0..64")
    for name in env or []:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise ValueError(f"bad variable name {name!r}")
    info = detect(project_dir)
    notes = []
    browser = info["browser"] or ("any" if browser_lib else None)
    if pabot and not info["pabot"]:
        notes.append("robotframework-pabot is not in your requirements: the pipeline installs it; better pin it there")
    if ci in ("gitlab", "jenkins") and browser in ("any",):
        notes.append("pin robotframework-browser in requirements so the Docker image tag can match "
                     "(replace <ROBOTFRAMEWORK_BROWSER_VERSION>)")
    if info["rf"] and tuple(int(x) for x in info["rf"].split(".")[:2]) < (7, 0):
        notes.append(f"Robot Framework {info['rf']} is pinned: 7.x brings VAR, GROUP, typed and secret variables "
                     "(see robotframework-test-authoring)")
    o = {"tests": tests, "pabot": pabot, "rerun": rerun, "include": include, "variablefile": variablefile,
         "env": list(env or []), "browser": browser, "requirements": info["requirements"], "has_pabot": info["pabot"]}
    return GENERATORS[ci](o), notes, info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ci", required=True, choices=sorted(GENERATORS))
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--tests", default="tests", help="suite folder or file (default tests)")
    ap.add_argument("--pabot", type=int, default=0, metavar="N", help="run in parallel with pabot and N processes")
    ap.add_argument("--no-rerun", action="store_true", help="do not rerun failed tests")
    ap.add_argument("--include", help="tag pattern to run, e.g. smoke or 'smoke OR critical'")
    ap.add_argument("--variablefile", help="environment variable file, e.g. variables/staging.py")
    ap.add_argument("--env", action="append", default=[], metavar="NAME", help="secret/variable the tests read with %%{NAME}")
    ap.add_argument("--browser-lib", action="store_true", help="the suite uses the Browser library (even if not in requirements)")
    ap.add_argument("--out", help=f"write here (e.g. {', '.join(DEFAULT_OUT.values())}); default: print")
    ap.add_argument("--force", action="store_true")
    opts = ap.parse_args(argv)
    try:
        text, notes, info = generate(opts.ci, opts.project_dir, opts.tests, opts.pabot, not opts.no_rerun, opts.include,
                                     opts.variablefile, opts.env, opts.browser_lib)
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
    print(f"# Robot Framework: {info['rf'] or 'not pinned'}, Browser library: {info['browser'] or 'no'}, "
          f"pabot: {'yes' if info['pabot'] else 'no'}", file=sys.stderr)
    for n in notes:
        print(f"# note: {n}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
