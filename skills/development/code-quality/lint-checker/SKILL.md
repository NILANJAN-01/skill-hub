---
name: lint-checker
description: Lint code in any programming language. A bundled script detects the project's languages, the linters it configures and the ones installed, runs them (ruff, ESLint, golangci-lint, clippy, Gradle/Maven Checkstyle, PMD, SpotBugs, ktlint, detekt, Android Lint and more) in one report, and adds built-in checks needing no tools. Use when the user asks to lint, check code quality or style, or fix lint errors.
license: MIT
metadata:
  title: "Lint checker: find and run linters for any language"
  category: code-quality-tools
---

# Lint checker

Lint a project in whatever languages it uses. The project's own linter setup comes first: the configs, the versions it pins and its package scripts. The bundled script [scripts/lint_check.py](scripts/lint_check.py) (Python 3.8+, standard library only) finds that setup, runs the right tools, and reports exit codes and output together. When no linter is installed, its built-in checks still catch problems in every language:

| Built-in rule | Severity | Catches |
|---|---|---|
| `conflict-marker` | error | `<<<<<<<` / `=======` / `>>>>>>>` left after a merge (ignored inside Markdown code fences) |
| `syntax` | error | Python that does not compile, invalid JSON (JSONC files such as `tsconfig.json` are skipped), invalid TOML (Python 3.11+) |
| `debugger` | warning | `breakpoint()`, `pdb.set_trace()`, `debugger;`, `binding.pry`, `byebug`, `var_dump(`, `dd(`, `dbg!(`, and `e.printStackTrace()` in Java and Kotlin |
| `trailing-whitespace`, `final-newline`, `line-endings`, `mixed-indent` | warning | Whitespace problems, reported once per file with a count |
| `line-length` | info | Lines over `--max-line` characters (default 120; Markdown, JSON and data files are skipped) |

## When to use

- "Lint this", "run the linter", "check code quality or style", "why does CI's lint job fail", "fix the lint errors".
- Before committing or opening a pull request, on the changed files only.
- Setting up linting in a project that has none.
- A mixed-language repository where you don't know which tools apply.

## When NOT to use

- Design-level review (shallow modules, pass-through methods, vague names): use `software-design-guardrails`.
- Formatting only: run the project's formatter (`ruff format`, `prettier`, `gofmt`, `rustfmt`, `ktlint --format`).
- Running tests: use the unit-test skill for the language (`python-unit-test`, `kotlin-unit-test`, `junit-run-reports`).

## Safety rules

- `detect`, `basic` and `run` without `--fix` are read-only.
- `--fix` rewrites files. Ask the user first. Check that `git status` is clean, or commit or stash, so the fixes can be reviewed with `git diff` and undone. Without `--yes`, `run --fix` only prints the commands it would run.
- Never install a linter, add it to the project's dependencies, or create a lint config without asking. The `detect` output gives the install command so you can propose it.
- Never change linter configs or add suppression comments (`# noqa`, `// eslint-disable`, `#[allow]`, `@Suppress`) just to make errors go away. Fix the code. Suppress only a confirmed false positive, with the narrowest scope and a reason.
- Linters run with the project folder as the working directory and can execute project code (ESLint and Stylelint configs are JavaScript, and `cargo clippy` runs build scripts). Run them only on code you trust.

## Procedure

1. **Detect.** From the project root:
   ```bash
   python <skill-dir>/scripts/lint_check.py detect
   ```
   This lists the languages with file counts and every relevant linter, showing whether it is configured, whether it is installed and the plan. The rules are:
   - Linters the project configures (for example `[tool.ruff]` in `pyproject.toml`, `eslint.config.js`, `.golangci.yml`, `.rubocop.yml`) are always planned. If one is not installed, that is reported.
   - When a language has no configured linter, the first installed default runs (for example ruff, then flake8). Type checkers (mypy, tsc) and tools that need a config (ESLint 9, Stylelint, sqlfluff, clang-tidy, phpstan) run only when configured.
   - Node tools are taken from `node_modules/.bin` before `PATH`, so the project's pinned version is used.
   - `--only ruff,eslint` picks tools by hand. `--all` runs every installed applicable tool. `python lint_check.py list` shows every id.
2. **Prefer the project's own lint command** when there is one. It is what CI runs. Check `package.json` scripts (`npm run lint`), `Makefile` / `justfile` targets, `tox.ini` / `noxfile.py`, `.pre-commit-config.yaml` (`pre-commit run --all-files`), and CI workflow files. Gradle and Maven lint plugins are already run by the script (see [Java and Kotlin](#java-and-kotlin)). See [references/linters.md](references/linters.md). Use the script for what those don't cover, or when they don't exist.
3. **Run.**
   ```bash
   python <skill-dir>/scripts/lint_check.py run                  # whole project
   python <skill-dir>/scripts/lint_check.py run --changed        # files changed since HEAD, plus untracked files
   python <skill-dir>/scripts/lint_check.py run --changed origin/main --format json
   ```
   Each linter prints its command, status and output (trimmed to `--max-output` lines), followed by the built-in findings and a summary. Exit codes: `0` OK, `1` FAIL (a linter failed, or a built-in finding reached `--fail-on`, default `error`), `3` INCOMPLETE (nothing failed but a planned linter is not installed), `2` usage error.
4. **Read the results before you change anything.** Group findings by rule and count them. Separate real bugs (unused or undefined names, unreachable code, unchecked errors, wrong comparisons) from style issues. If a linter fails on its own config or crashes (output about a missing config, plugin or module instead of file:line findings), fix the setup first. For a big legacy backlog, propose linting only changed lines (`--changed`) or a baseline instead of mass edits.
5. **Fix.** Ask first, then apply the safe automatic fixes:
   ```bash
   python <skill-dir>/scripts/lint_check.py run --fix            # prints the plan only
   python <skill-dir>/scripts/lint_check.py run --fix --yes      # applies it
   ```
   Fix the rest by hand, one rule at a time, keeping behaviour unchanged. "Unsafe" fixes (ruff `--unsafe-fixes`, `rubocop -A`) can change behaviour. Use them only when asked, and review the diff.
6. **Verify.** Run `run` again (and the tests, if fixes touched logic) until the result is OK. Show the user `git diff --stat`.
7. **Report.** Give the commands that ran, counts before and after per linter, what was fixed automatically and what by hand, anything left with a reason, and any linter that did not run (INCOMPLETE) with its install command.

## Java and Kotlin

JVM projects lint through their build, so the script does too.

- **`gradle-lint`** reads every `*.gradle`, `*.gradle.kts` and `*.versions.toml` file (root, subprojects, `buildSrc`, `build-logic`) for applied lint plugins, then runs their tasks in **one** Gradle call with `--continue`, so one failing tool does not hide the others:

  | Plugin | Check task | Fix task |
  |---|---|---|
  | `checkstyle` (core) | `checkstyleMain` | none |
  | `pmd` (core) | `pmdMain` | none |
  | `com.github.spotbugs` | `spotbugsMain` | none |
  | `org.jlleitschuh.gradle.ktlint` | `ktlintCheck` | `ktlintFormat` |
  | `org.jmailen.kotlinter` | `lintKotlin` | `formatKotlin` |
  | `io.gitlab.arturbosch.detekt` | `detekt` | none |
  | `com.diffplug.spotless` | `spotlessCheck` | `spotlessApply` |
  | `com.android.application` / `library` | `lint` (Android Lint) | `lintFix` |

- **`maven-lint`** does the same from `pom.xml` files: `checkstyle:check`, `pmd:check`, `compile spotbugs:check`, `ktlint:check`, `detekt:check` and `spotless:check` (fixes: `ktlint:format`, `spotless:apply`), run with `-B -fae`.
- The project's wrapper (`gradlew`, `gradlew.bat`, `mvnw`, `mvnw.cmd`) is used before `gradle` or `mvn` on `PATH`. A JDK is needed. The first run can be slow while Gradle downloads dependencies, so raise `--timeout` if needed.
- When the build applies lint plugins, the standalone CLIs (`checkstyle`, `pmd`, `ktlint`, `detekt`) are not also run, because CI runs the build's version with the build's config. With no lint plugin in the build, an installed standalone CLI runs instead: `checkstyle` with `checkstyle.xml` or `config/checkstyle/checkstyle.xml` if present, otherwise Google style.
- The console output only summarises. The full findings are in the reports Gradle and Maven print paths to, for example `build/reports/checkstyle/main.html`, `build/reports/detekt/detekt.html`, `build/reports/lint-results-debug.html`, `target/checkstyle-result.xml` and `target/spotbugsXml.xml`. Read those reports to list the file, line and rule for each finding.
- Compiler warnings are a lint pass too: `./gradlew compileJava compileKotlin --warning-mode all`, `-Xlint:all` for javac, and `allWarningsAsErrors` for Kotlin.

## Setting up linting where there is none

Propose one standard tool per language, with a minimal config, and ask before adding anything. Defaults and config snippets are in [references/linters.md](references/linters.md). Start from the tool's recommended rule set, run it once, and fix or explicitly disable whatever produces only noise. Then wire the same command into pre-commit and CI so humans, agents and CI all run identical checks.

## Monorepos

Configs are looked up at the folder you pass. In a monorepo, run `detect` and `run` once per package (`python lint_check.py run packages/web`), or use the workspace's own lint command. `list_files` honours `.gitignore` and skips `node_modules`, virtualenvs, `build`, `dist`, `target`, `vendor` and similar folders.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `result: INCOMPLETE`, `missing - install: ...` | The linter is configured but not installed. Install project dependencies (`npm ci`, `pip install -e .[dev]`, `bundle install`) or the tool, then rerun. Report it if you can't install |
| ESLint: `couldn't find an eslint.config file` | ESLint 9 needs a flat config. Migrate with `npx @eslint/migrate-config .eslintrc.json`, or use the project's pinned ESLint 8 |
| A linter fails with a stack trace or "unknown option" | Version mismatch. Use the project's pinned version (`npx`, `node_modules/.bin`, `uv run`, `poetry run`, `bundle exec`) |
| `needs go.mod at the project root` (or Cargo.toml, pubspec.yaml, .sln) | Pass the sub-project folder: `run path/to/module` |
| `gradle-lint: missing - no gradlew wrapper ...` | Install Gradle (or Maven) and a JDK, or generate the wrapper with `gradle wrapper` (ask first) |
| Gradle: `Task 'ktlintCheck' not found` | The plugin is declared in a version catalog or with `apply false` but never applied. Apply it in the module, or run with `--only` and other tools |
| Gradle fails with `Unsupported class file major version` | The JDK is too new or too old for the build. Use the JDK the project targets (`JAVA_HOME`, toolchains) |
| `syntax` error on valid new Python | The check uses the Python that runs the script. Run it with the project's Python version |
| Thousands of findings on old code | Run with `--changed`, add a baseline if the tool supports one, or fix one rule at a time |
| `timed out after 600s` | Raise `--timeout`, or lint fewer files with `--changed` |
| Built-in `mixed-indent` or `line-endings` warnings | Add a `.editorconfig` and a `.gitattributes` (`* text=auto`), then renormalise with `git add --renormalize .` (ask first) |

## References

- [references/linters.md](references/linters.md): per-language linters, configs, fix commands, build-tool and pre-commit and CI wiring.
- [scripts/lint_check.py](scripts/lint_check.py): the detector, runner and built-in checks (`--help` for every option).
