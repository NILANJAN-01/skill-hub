# Health audit: rules and scoring

The audit reads the code (comments removed; string contents also removed for rules that look only at code), build files and the file list. It never runs anything and never opens files named like credentials.

## Score

- Seven areas, each starting at 100: Security 25%, Code health 20%, Tests 15%, Design 15%, Documentation 10%, Build & dependencies 10%, Repository hygiene 5%. The overall score is the weighted mean. Grades: A 90+, B 80+, C 70+, D 60+, F below.
- Each rule found takes points from its area once: HIGH 15, MEDIUM 6, LOW 2, unless the table gives its own number. Each repeat adds a quarter more, up to twice the base, so a thousand TODOs do not sink a project.
- Findings in test code drop one severity level (LOW ones are dropped) and weigh half.
- Dismissed findings (in `annotations.json`) do not count, and are listed with their reason.

## Rules

| Rule | Area | Severity | Finding | Fix |
|---|---|---|---|---|
| SEC001 | Security | HIGH (30 points) | Hard-coded secret: private key block, cloud and API tokens, password in a URL, or a secret-named setting with a random-looking value (placeholders ignored; shown masked) | Remove it from the code and history, rotate it, and read it from the environment or a secret store. |
| SEC002 | Security | MEDIUM (12 points) | File named like a credential (`.env`, `*.pem`, `*.key`, `id_rsa`...) | Check it (it was not opened). If it holds a secret: remove it, rotate the secret, ignore the name and commit an .example copy. |
| SEC003 | Security | MEDIUM | Code run from a string (eval/exec) | Replace with explicit parsing or a lookup table; never pass outside input to it. |
| SEC004 | Security | MEDIUM | Shell command built from a string (`shell=True`, `os.system`, `Runtime.exec`, `sh -c`, `system()`) | Pass an argument list without a shell (shell=False, exec.Command with separate args, ProcessBuilder). |
| SEC005 | Security | MEDIUM | Unsafe deserialization (pickle, `yaml.load`, `ObjectInputStream`, `BinaryFormatter`, `unserialize`) | Use a data-only format (JSON) or a safe loader; never unpickle or deserialize untrusted input. |
| SEC006 | Security | HIGH | gets() reads without a bound | Use fgets() with the buffer size. |
| SEC007 | Security | MEDIUM | Unbounded C string function (`strcpy`, `strcat`, `sprintf`, `scanf("%s")`); skipped when the repository defines its own function of that name | Use bounded versions (snprintf, strlcpy or std::string) and check sizes. |
| SEC008 | Security | HIGH | TLS certificate check turned off (`verify=False`, `InsecureSkipVerify`, `rejectUnauthorized: false`, trust-all managers) | Keep verification on; trust a private CA with a CA bundle instead. |
| SEC009 | Security | HIGH | SQL built by string formatting (concatenation, f-strings, `%`, `format`, `Sprintf`) | Use parameterized queries (placeholders and bound values). |
| SEC010 | Security | LOW | Weak hash (MD5/SHA-1) | Use SHA-256 or better for anything security related; mark checksum-only uses as such. |
| SEC011 | Security | LOW | Plain http:// URL to a remote host | Use https:// for remote hosts. |
| SEC012 | Security | MEDIUM | Debug mode enabled in code | Read the debug flag from configuration and keep it off in production. |
| COD001 | Code health | MEDIUM | Very large file (over 1,000 lines) | Split it by responsibility into smaller modules. |
| COD002 | Code health | MEDIUM | Long function (over 100 lines) | Extract steps into well-named helper functions. |
| COD003 | Code health | LOW | Deeply nested code (over 4 levels in Python, 6 braces elsewhere) | Return early, extract inner blocks, or use a lookup table. |
| COD004 | Code health | MEDIUM | Error swallowed silently (empty `catch`, `except: pass`, empty `if err != nil {}`) | Handle the error, log it, or let it propagate; catch only the specific exception expected. |
| COD005 | Code health | LOW | TODO/FIXME/HACK/XXX left in code | Fix it or move it to the issue tracker. |
| COD006 | Code health | LOW | Too many parameters (over 7) | Group related parameters into an object or split the function. |
| TST001 | Tests | HIGH (60 points) | No tests found (200+ code lines) | Add an automated test suite for the core logic and run it in CI. |
| TST002 | Tests | MEDIUM (15 points) | Little test code (under 10% of code lines) | Add tests for the main flows; aim for tests growing with the code. |
| TST003 | Tests | LOW | Component of 300+ lines that no test imports or names | Add tests that import this component. |
| DES001 | Design | MEDIUM (12 points) | Dependency cycle between components | Move the shared part into a lower component, or depend on an interface. |
| DES002 | Design | LOW | Oversized (over half the code) or over-connected (imports 8+ components) component | Split it along its responsibilities. |
| DES003 | Design | LOW | Possibly unused private function (its name appears nowhere else) | Delete it if nothing calls it (check for dynamic use first). |
| DOC001 | Documentation | HIGH (50 points) | No README | Add a README: what it is, how to build, run and test it. |
| DOC002 | Documentation | MEDIUM | README is very short (under 400 characters) | Explain purpose, setup, usage and how to contribute. |
| DOC003 | Documentation | MEDIUM (20 points) | No license file | Add a LICENSE file so others know how they may use the code. |
| DOC004 | Documentation | LOW | README has no build or usage section | Add install, build, run and test commands. |
| DOC005 | Documentation | LOW | Large file with almost no comments (under 2% of 300+ lines) | Document the purpose of the module and its non-obvious parts. |
| BLD001 | Build & dependencies | MEDIUM (25 points) | No CI configuration | Add a CI workflow that builds and runs the tests on every change. |
| BLD002 | Build & dependencies | LOW | No build or dependency manifest for a language with 3+ files | Declare the build and dependencies (pyproject, package.json, go.mod, CMakeLists, build.gradle...). |
| DEP001 | Build & dependencies | LOW | Dependency without a version | Pin a version or a range, and commit a lock file. |
| DEP002 | Build & dependencies | LOW | No lock file (npm, Poetry, Cargo applications, Go, Bundler, Composer) | Commit the lock file so builds are reproducible. |
| DEP003 | Build & dependencies | MEDIUM | Wildcard or latest dependency version (`*`, `latest`, Gradle `+`, Maven `LATEST`) | Replace '*', 'latest' or '+' with a real version or range. |
| HYG001 | Repository hygiene | LOW | No .gitignore | Add a .gitignore for build output, caches and local files. |
| HYG002 | Repository hygiene | MEDIUM | Build output or dependencies committed (`node_modules`, `__pycache__`, `.class`, `.o`, `.dll`...) | Delete them from git and ignore the folder. |
| HYG003 | Repository hygiene | LOW | Very large file in the repository (over 5 MB) | Move big binaries to releases, Git LFS or artifact storage. |
| HYG004 | Repository hygiene | HIGH (30 points) | Unresolved merge conflict markers | Resolve the conflict and remove the markers. |

## Limits

Patterns find likely problems, not proven ones: a `shell=True` with a constant command is safe, and an injection hidden behind a helper function is missed. The audit is not a substitute for a security review, a linter or real test coverage.
