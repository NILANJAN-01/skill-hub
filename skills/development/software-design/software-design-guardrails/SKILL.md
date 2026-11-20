---
name: software-design-guardrails
description: "Make AI coding agents follow good software design on every change: always-on design rules for a project's agent instruction files, a pre-commit hook and CI, and a checker that flags red flags (pass-through methods, shallow functions, swallowed errors, duplicated code, vague names, comments that repeat code) in changed lines. Use when writing, refactoring or reviewing code, or when the user wants simple, maintainable code enforced."
license: MIT. Original summary of ideas from A Philosophy of Software Design by John Ousterhout (2018); no text from the book is reproduced. See THIRD_PARTY_NOTICES.md
compatibility: Needs Python 3.8+ (standard library only) for the scripts and git for --diff, --staged and the hook. Works with any agent. The checker parses Python fully and Java, Kotlin, C#, Go, JS/TS, C/C++, Rust, Swift, Dart, Scala and PHP with heuristics.
metadata:
  title: "Software design guardrails: rules, checker, hook and CI"
  category: software-design-tools
  source: "A Philosophy of Software Design, John Ousterhout, 2018"
  pages: "Whole book; Summary of Design Principles; Summary of Red Flags"
---

# Software design guardrails

The goal of software design is to keep complexity low: code that is easy to understand and safe to change. Complexity shows up as *change amplification* (one change touches many places), *cognitive load* (too much to know before changing anything) and *unknown unknowns* (you cannot tell what else must change). It comes from *dependencies* and *obscurity*, and it accumulates in small steps, so every change matters.

This skill is the always-on part of the software-design set. It gives an agent three things:

1. **Rules** that are loaded at the start of every session: [assets/guardrails-block.md](assets/guardrails-block.md).
2. **A checker** for the red flags a script can see: `scripts/design_check.py`.
3. **Enforcement** that does not depend on anyone remembering: a pre-commit hook and a CI step.

## When to use

- Any task that writes or changes code: apply the per-change workflow below.
- The user wants AI-written code to be simple, clean or maintainable "by default".
- Setting up a repository so every agent and teammate follows the same design rules.
- Reviewing a diff or pull request for design quality.

## When NOT to use

- One-off scripts that are run once and thrown away: a quick manual pass over the rules is enough.
- Deep work on one topic: load `deep-modules` (module and API shape), `error-handling-design`, `obvious-code` (comments and names) or `design-it-twice` (planning, performance).
- Style and formatting (indentation, brace placement): use the project's formatter and linter.

## Per-change workflow (follow on every coding task)

**Before writing code**
1. Read the code around the change. Note the conventions: naming, file layout, error style, comment style. New code follows them, even where you would choose differently.
2. If the change adds a module, class, public function or API, design it twice: sketch two different interfaces and pick the one that is simplest for callers (`design-it-twice`). Write the interface comment before the body.

**While writing code**, apply the twelve rules in [assets/guardrails-block.md](assets/guardrails-block.md). In short: deep modules, no pass-throughs, hide each decision in one place, simple common case, pull complexity down, general core with special cases at the edges, define errors away, comments that add information, precise names, obvious code, fix what you touch, and measure before optimising.

**Before finishing**
1. Run the checker on the changed lines:
   ```bash
   python scripts/design_check.py --diff            # working tree + untracked files vs HEAD
   python scripts/design_check.py --diff main       # everything since the branch left main
   ```
2. For each finding, either fix it or keep the code and justify it next to the code:
   `# design-check: ignore[pass-through-method] -- adapter required by the plugin API`.
   Never silence a finding without a reason.
3. Review the diff by hand for the red flags no script can see (table below).
4. In your summary, list any design debt you left on purpose and why.

## Install the guardrails into a project

Agents read instruction files at session start, so the rules apply without being asked. The installer writes one marked block into `AGENTS.md` (the shared instruction file many agents read) and into any other agent instruction file the project already has, unless that file only points at `AGENTS.md`. It also copies the checker into the project so CI and teammates run the same version.

```bash
python scripts/install_guardrails.py status  --project <repo>
python scripts/install_guardrails.py install --project <repo>                # dry run: shows the plan
python scripts/install_guardrails.py install --project <repo> --hook --yes   # block + tools/design_check.py + pre-commit hook
python scripts/install_guardrails.py remove  --project <repo> --hook --yes
```

- Show the dry-run plan to the user and get agreement before `--yes`. The script never writes without it.
- `--vendor <dir>` puts the checker somewhere other than `tools/`. `--no-vendor` references this skill's copy by absolute path, which works on this machine only.
- `--also <file>` adds the block to another instruction file, for example a rules file in an agent-specific folder.
- An existing pre-commit hook that the script did not write is never replaced. The script prints the line to add to it instead.
- Re-running `install` updates the block in place. Edit the wording in `assets/guardrails-block.md`, not in the project.

For CI (GitHub Actions, GitLab CI, the pre-commit framework) and for adopting the checker on a large existing code base with a baseline, see [references/ci.md](references/ci.md).

## The checker

```bash
python scripts/design_check.py [PATH ...]           # whole tree (default .)
python scripts/design_check.py --diff [REF]         # only lines changed since REF (default HEAD)
python scripts/design_check.py --staged             # only staged lines (what the hook runs)
python scripts/design_check.py --list-rules         # every rule with its red flag and fix
```

Options: `--format json`, `--fail-on warning|info|never` (default `warning`), `--select` / `--ignore` with rule ids, `--baseline FILE` / `--write-baseline FILE`, `--include-tests`. Exit codes: `0` clean, `1` findings at or above `--fail-on`, `2` usage or git error. It only reads files, except for `--write-baseline`.

| Rule | Severity | Red flag |
|---|---|---|
| `pass-through-method` | warning | Method only forwards its arguments to another method |
| `pass-through-variable` | warning | Parameter threaded through two or more layers that never use it |
| `long-parameter-list` | warning | Overexposure: more than 4 required or 8 total parameters |
| `swallowed-error` | warning | Empty handler with no comment saying why |
| `duplicate-code` | warning | Six or more meaningful lines repeated |
| `single-use-shallow` | info | One-line function with a single call site |
| `trivial-accessor` | info | Plain getter or setter |
| `repeated-handler` | info | Same error handler three or more times in a file |
| `comment-repeats-code`, `doc-repeats-name` | info | Comment restates the code or the name |
| `missing-interface-doc` | info | Public class or function without an interface comment |
| `impl-in-interface-doc` | info | Interface comment describes the implementation |
| `vague-name`, `non-predicate-boolean` | info | `data`, `tmp`, `result` with no return value, `soundStatus` |
| `generic-container` | info | Returns a pair or a 3+ tuple instead of a named type |
| `tactical-marker` | info | `HACK`, `XXX`, `FIXME`, "quick fix", "for now" |

Findings are prompts for judgement, not verdicts. Python is parsed exactly. Other languages use text heuristics, so expect some misses and some false alarms.

## Red flags the checker cannot see (review by hand)

| Red flag | Ask |
|---|---|
| Information leakage | Does the same knowledge (a file format, a protocol, an ordering rule) appear in two modules? |
| Temporal decomposition | Are modules split by *when* things happen (read, then process, then write) rather than by what they know? |
| Overexposure | Must a caller learn about rare options to do the common thing? |
| Special-general mixture | Does a general mechanism contain code for one particular use? |
| Conjoined methods | Can you understand one function without reading another one? |
| Hard to describe | Does the interface comment need many paragraphs or many caveats? |
| Hard to pick name | Is there no short precise name? The thing may not be one coherent idea. |
| Nonobvious code | Would a first-time reader guess the behaviour correctly? |

Every red flag with its symptoms, fixes and the skill that covers it: [references/red-flags.md](references/red-flags.md). The fifteen principles behind them: [references/principles.md](references/principles.md).

## Safety rules

- Do not edit a project's instruction files, hooks or CI without the user's agreement. Show the dry run first.
- Do not "fix" findings by deleting behaviour, tests or error handling. A finding is a reason to restructure, not to remove.
- Do not mass-reformat or rename across a code base to clear findings. Fix the code you are changing, and adopt older code with a baseline.
- Keep the rules short. The block costs context in every session. Put detail in this skill's references, not in the block.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `git error` with `--diff` or `--staged` | Run inside a git repository, or scan paths without `--diff` |
| Hundreds of findings on old code | `--write-baseline .design-baseline.json` once, then run with `--baseline` (see [references/ci.md](references/ci.md)) |
| A false alarm in a language other than Python | Add `design-check: ignore[<rule>] -- <reason>`. The heuristics prefer missing a case to flagging valid code |
| The hook does not run | `install_guardrails.py status`; check `core.hooksPath`; the hook needs `python3` or `python` on PATH |
| The agent ignores the rules | Confirm the block is in a file this agent reads (`status`), restart the session, keep the block short |
| `skipped (could not parse)` | The Python file has a syntax error for this interpreter version. Run the checker with the project's Python |

## Related skills

- `deep-modules`: interface depth, information hiding, splitting and merging code.
- `error-handling-design`: defining errors out of existence, masking, aggregation.
- `obvious-code`: comments, names, consistency, readable code.
- `design-it-twice`: comparing designs before coding, strategic programming, performance.
- Linters, formatters and code-review tools handle correctness and style, which this set does not cover.

## Source

Based on the ideas in *A Philosophy of Software Design* by John Ousterhout (Yaknyam Press, 2018), especially chapters 2 and 3, the Summary of Design Principles and the Summary of Red Flags. This skill summarises those ideas in its own words and adds original tooling. Read the book for the full reasoning and examples.
