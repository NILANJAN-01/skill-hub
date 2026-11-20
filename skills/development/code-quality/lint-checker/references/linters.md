# Linters by language

Read this when choosing, installing, configuring or wiring up a linter. Prefer what the project already uses. The ids match `lint_check.py list`.

## Contents

- [Quick table](#quick-table)
- [Language notes and minimal configs](#language-notes-and-minimal-configs)
- [Build-tool lint tasks (JVM, .NET, Android)](#build-tool-lint-tasks-jvm-net-android)
- [Running the project's pinned version](#running-the-projects-pinned-version)
- [pre-commit and CI](#pre-commit-and-ci)
- [Suppressing a finding properly](#suppressing-a-finding-properly)

## Quick table

| Language | Default linter (id) | Check | Auto-fix | Install |
|---|---|---|---|---|
| Python | ruff | `ruff check .` | `ruff check --fix .` | `pip install ruff` |
| Python (types) | mypy | `mypy .` | none | `pip install mypy` |
| JavaScript / TypeScript | eslint (needs config) or biome | `npx eslint .` / `npx biome lint .` | `--fix` / `--write` | `npm i -D eslint` / `npm i -D -E @biomejs/biome` |
| TypeScript (types) | tsc | `npx tsc --noEmit -p .` | none | `npm i -D typescript` |
| Go | golangci-lint, else go-vet | `golangci-lint run ./...` | `golangci-lint run --fix ./...` | see golangci-lint.run |
| Rust | clippy | `cargo clippy --all-targets -- -D warnings` | `cargo clippy --fix --allow-dirty` | `rustup component add clippy` |
| Java | gradle-lint / maven-lint (build plugins), else pmd, checkstyle | `./gradlew --continue checkstyleMain pmdMain spotbugsMain` / `mvn checkstyle:check pmd:check` | `spotlessApply` | Checkstyle, PMD, SpotBugs, Spotless plugin, or the CLI |
| Kotlin | gradle-lint / maven-lint, else ktlint, detekt | `./gradlew --continue ktlintCheck detekt` / `ktlint` | `ktlintFormat` / `ktlint --format` | ktlint, kotlinter, detekt plugin, or the CLI |
| Android | gradle-lint (Android Lint) | `./gradlew lint` | `./gradlew lintFix` | Android Gradle Plugin |
| C / C++ | cppcheck, clang-tidy (needs `.clang-tidy`) | `cppcheck --enable=warning,style .` | `clang-tidy --fix` | LLVM tools, cppcheck |
| C# | dotnet-format | `dotnet format --verify-no-changes` | `dotnet format` | .NET SDK |
| Ruby | rubocop | `rubocop` | `rubocop -a` (safe), `-A` (unsafe) | `gem install rubocop` |
| PHP | phpstan, phpcs (need config) | `vendor/bin/phpstan analyse` | `vendor/bin/phpcbf` | composer |
| Shell | shellcheck | `shellcheck script.sh` | none (read the SC code page) | package manager |
| PowerShell | psscriptanalyzer | `Invoke-ScriptAnalyzer -Path . -Recurse` | `-Fix` | `Install-Module PSScriptAnalyzer` |
| Swift | swiftlint | `swiftlint lint` | `swiftlint --fix` | `brew install swiftlint` |
| Dart / Flutter | dart-analyze | `dart analyze` (`flutter analyze`) | `dart fix --apply` | SDK |
| Lua | luacheck | `luacheck .` | none | `luarocks install luacheck` |
| CSS / SCSS | stylelint (needs config) | `npx stylelint "**/*.css"` | `--fix` | `npm i -D stylelint stylelint-config-standard` |
| YAML | yamllint | `yamllint .` | none | `pip install yamllint` |
| Markdown | markdownlint | `npx markdownlint-cli2 "**/*.md"` | `--fix` | `npm i -D markdownlint-cli2` |
| Dockerfile | hadolint | `hadolint Dockerfile` | none | binary or `docker run --rm -i hadolint/hadolint < Dockerfile` |
| Terraform | tflint | `tflint --recursive` | `--fix` | see the tflint repository |
| SQL | sqlfluff (needs config or `--dialect`) | `sqlfluff lint --dialect postgres .` | `sqlfluff fix` | `pip install sqlfluff` |
| Haskell | hlint | `hlint .` | `--refactor` | `cabal install hlint` |
| Elixir | credo | `mix credo --strict` | none | dep in `mix.exs` |

For GitHub Actions workflows, `actionlint` is worth adding. For GitLab CI files, use the `gitlab-ci-*` skills.

## Language notes and minimal configs

### Python: ruff

Ruff replaces flake8, isort, pyupgrade and most pylint checks, and runs fast. Minimal `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py39"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP"]   # pycodestyle, pyflakes, isort, bugbear, pyupgrade
```

`F401` unused import, `F841` unused variable and `B006` mutable default are real bugs or waste. `E501` is style. `ruff rule F401` explains a rule. Use `ruff check --statistics` for a count per rule.

### JavaScript / TypeScript: ESLint 9 or Biome

ESLint 9 needs a flat config, `eslint.config.js`:

```js
import js from "@eslint/js";
import tseslint from "typescript-eslint";
export default tseslint.config(js.configs.recommended, ...tseslint.configs.recommended,
  { ignores: ["dist/", "build/", "coverage/"] });
```

Biome is one fast binary for linting and formatting with no plugins: `npx @biomejs/biome init` writes `biome.json`. Don't run two JS linters with overlapping rules. Type errors come from `tsc --noEmit`, not from the linter.

### Go: golangci-lint

It bundles `govet`, `staticcheck`, `errcheck`, `ineffassign` and `unused` by default. Minimal `.golangci.yml` (v2 format):

```yaml
version: "2"
linters:
  enable: [gosec, revive]
```

Without it, `go vet ./...` (and `staticcheck ./...` if installed) is the baseline.

### Rust: clippy

`-D warnings` makes warnings fail like CI does. Configure lints in `Cargo.toml`:

```toml
[lints.clippy]
pedantic = { level = "warn", priority = -1 }
```

### Java and Kotlin: lint plugins in the build

Add plugins to the build so local runs, agents and CI share one config. Gradle Kotlin DSL (check plugin versions on the Gradle Plugin Portal before adding):

```kotlin
plugins {
    java
    checkstyle                                             // config/checkstyle/checkstyle.xml
    pmd
    id("com.github.spotbugs") version "6.0.26"
    id("org.jlleitschuh.gradle.ktlint") version "12.1.1"   // Kotlin style, uses .editorconfig
    id("io.gitlab.arturbosch.detekt") version "1.23.7"     // Kotlin smells, config/detekt/detekt.yml
}

checkstyle { toolVersion = "10.20.1"; maxWarnings = 0 }
pmd { toolVersion = "7.7.0"; ruleSetFiles = files("config/pmd/ruleset.xml"); ruleSets = listOf() }
detekt { buildUponDefaultConfig = true }
```

`./gradlew detektGenerateConfig` writes a starting detekt config. Checkstyle ships `google_checks.xml` and `sun_checks.xml` to copy from. For an existing codebase, `detektBaseline` and ktlint's `ktlintGenerateBaseline` record the current findings so only new ones fail.

Maven `pom.xml` (inside `<build><plugins>`):

```xml
<plugin>
  <groupId>org.apache.maven.plugins</groupId>
  <artifactId>maven-checkstyle-plugin</artifactId>
  <version>3.6.0</version>
  <configuration>
    <configLocation>google_checks.xml</configLocation>
    <violationSeverity>warning</violationSeverity>
  </configuration>
</plugin>
<plugin>
  <groupId>org.apache.maven.plugins</groupId>
  <artifactId>maven-pmd-plugin</artifactId>
  <version>3.26.0</version>
</plugin>
```

Common Java findings worth fixing first: unused imports and variables, empty `catch` blocks, `printStackTrace()` instead of logging, `equals` without `hashCode`, resources not closed (use try-with-resources), and comparing strings with `==`. Common Kotlin ones: `!!` on values that can be null, unused parameters, wildcard imports, long parameter lists, and swallowed exceptions.

Android Lint reads `lint.xml` (or `android { lint { ... } }`). `abortOnError`, `warningsAsErrors` and `baseline = file("lint-baseline.xml")` control what fails the build. Reports go to `app/build/reports/lint-results-<variant>.html`. `./gradlew lintDebug` checks a single variant, which is faster.

### C / C++

clang-tidy needs `compile_commands.json`. With CMake, `cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON`. With other builds, use `bear -- make`. cppcheck works without one. Also compile with `-Wall -Wextra` (or `/W4` on MSVC). Compiler warnings are the first lint pass.

### Shell: ShellCheck

Each finding has a code (`SC2086`: unquoted variable) with a wiki page. Add a shebang or `# shellcheck shell=bash` so it knows the dialect.

## Build-tool lint tasks (JVM, .NET, Android)

On the JVM, lint runs through the build, so use the project's tasks:

| Tool | Gradle | Maven |
|---|---|---|
| Checkstyle | `./gradlew checkstyleMain` (plugin `checkstyle`) | `mvn checkstyle:check` |
| PMD | `./gradlew pmdMain` (plugin `pmd`) | `mvn pmd:check` |
| SpotBugs | `./gradlew spotbugsMain` | `mvn spotbugs:check` |
| ktlint | `./gradlew ktlintCheck` / `ktlintFormat` | ktlint Maven plugin |
| detekt | `./gradlew detekt` | detekt Maven plugin |
| Spotless (format) | `./gradlew spotlessCheck` / `spotlessApply` | `mvn spotless:check` |
| Android Lint | `./gradlew lint` (report in `build/reports/lint-results-*.html`) | n/a |

`./gradlew check` usually runs all of them plus tests. Use `./gradlew tasks --all | grep -i -E "lint|check|detekt|style"` to see what exists. On Windows, use `gradlew.bat`. For Gradle setup problems, see `gradle-android`.

In .NET, analyzers run during `dotnet build`. Set `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>` and `<AnalysisLevel>latest-recommended</AnalysisLevel>` in the project file, and configure severities in `.editorconfig`.

## Running the project's pinned version

| Ecosystem | Command form |
|---|---|
| Node | `npx --no-install eslint .`, `npm run lint`, `pnpm exec`, `yarn` |
| Python | `uv run ruff check .`, `poetry run`, `pipx run ruff`, or the virtualenv's interpreter |
| Ruby | `bundle exec rubocop` |
| PHP | `vendor/bin/phpstan` |
| Go | the version pinned in CI, or `go run github.com/golangci/golangci-lint/v2/cmd/golangci-lint@vX.Y.Z run` |

Different versions report different findings, so match CI's version before arguing with a CI failure.

## pre-commit and CI

[pre-commit](https://pre-commit.com) runs the same hooks locally and in CI. A minimal `.pre-commit-config.yaml` (run `pre-commit autoupdate` to pin current versions):

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks: [{id: trailing-whitespace}, {id: end-of-file-fixer}, {id: check-merge-conflict},
            {id: check-json}, {id: check-yaml}]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks: [{id: ruff, args: [--fix]}]
```

Install it with `pre-commit install`, and run everything with `pre-commit run --all-files`.

The bundled script also works as a CI step with no dependencies:

```bash
python lint_check.py run --format json > lint-report.json   # exit 1 fails the job, 3 = a tool is missing
```

## Suppressing a finding properly

Suppress only after confirming a false positive, on one line, with the rule id and a reason:

| Tool | Line-level form |
|---|---|
| ruff / flake8 | `x = eval(s)  # noqa: S307 -- input is a constant table` |
| ESLint | `// eslint-disable-next-line no-console -- CLI output` |
| Biome | `// biome-ignore lint/suspicious/noConsole: CLI output` |
| golangci-lint | `//nolint:errcheck // close error is irrelevant for read-only file` |
| clippy | `#[allow(clippy::too_many_arguments)] // mirrors the C API` |
| Kotlin / detekt | `@Suppress("MagicNumber")` |
| RuboCop | `# rubocop:disable Style/X` ... `# rubocop:enable Style/X` |
| ShellCheck | `# shellcheck disable=SC2086  # word splitting intended` |
| Java (PMD / Checkstyle) | `@SuppressWarnings("PMD.X")` / `// CHECKSTYLE:OFF` |

Never disable a rule for a whole file or project without the user's agreement.
