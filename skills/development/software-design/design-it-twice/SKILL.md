---
name: design-it-twice
description: "Plan code before writing it: compare two or more genuinely different designs, write the interface comments first, then implement. Also covers strategic vs tactical programming, keeping the design clean while changing existing code, and designing for performance (measure first, critical path). A script scaffolds and checks the design note. Use when about to build a new module, class, API or feature, or when tempted to patch around a design problem."
license: MIT. Original summary of ideas from A Philosophy of Software Design by John Ousterhout (2018); no text from the book is reproduced. See THIRD_PARTY_NOTICES.md
compatibility: Needs Python 3.8+ (standard library only) for scripts/design_note.py. Works with any agent and language.
metadata:
  title: "Design it twice: plan, comment first, stay strategic"
  category: software-design-tools
  source: "A Philosophy of Software Design, John Ousterhout, 2018"
  pages: "Chapters 3, 11, 15, 16, 19, 20"
---

# Design it twice

First ideas are rarely the best design, for people and for models alike. Before building anything non-trivial, sketch at least two **genuinely different** designs, compare them, and pick or combine. This costs minutes to hours and saves days of building the wrong thing. It also builds judgement, because comparing designs teaches what makes one better.

## When to use

- Before writing a new module, class, service, public API, data format or major feature.
- Before a refactor that changes interfaces.
- When about to patch around a design problem in existing code ("just add a flag here").
- When performance work requires restructuring code.

## When NOT to use

- Small, local changes inside an existing, well-designed module: follow its design.
- Exploratory spikes that will be thrown away. Say so, and do not ship them.

## Procedure

1. **Frame the problem** from the callers' side: who calls this, and what do they need in their own words? List constraints and non-goals.
2. **Scaffold a design note** (it never overwrites an existing file):
   ```bash
   python scripts/design_note.py new "<what you are designing>" --alternatives 2 --out docs/design/<name>.md
   ```
   Without `--out` it prints to the terminal. Use that for small designs you only show in the conversation.
3. **Sketch two or more alternatives that differ in kind,** not in detail: a different unit of operation (per item vs per batch), a different owner of the hard part (caller vs module), push vs pull, stateful vs stateless. Even if one seems obviously right, sketch a second; its weaknesses show what matters. For each: the few key signatures, a few lines of calling code for the common case, what it hides, pros and cons.
4. **Compare** them on: simplicity of the interface for the common case (the most important criterion), generality, what each one hides or leaks, the errors and special cases callers must handle, and cost on the critical path. If none is attractive, use the problems you found to invent another. Often a combination wins.
5. **Decide** and write why. Then **write the interface comments before any code.** If a short, complete comment is hard to write, the abstraction is wrong: go back to step 3.
6. **Check the note:**
   ```bash
   python scripts/design_note.py check docs/design/<name>.md
   ```
   ERROR: fewer than two alternatives, missing sketch, pros or cons, no decision, empty interface comments, or unfilled markers. WARN: alternatives that are nearly identical, nothing hidden, red-flag items not reviewed.
7. **Implement** behind the commented interface. Apply design-it-twice again, at a smaller scale, to the implementation's data structures if they are not obvious.
8. Show the user the alternatives and the decision before or with the code. Ask before committing a design note to the repository.

## Strategic, not tactical

- *Tactical* work gets the feature done as fast as possible and accepts "just a little" extra complexity each time. *Strategic* work treats a clean design as the goal and working code as necessary but not sufficient.
- Invest continuously and in small amounts. Spend part of every task (the book suggests 10-20%) improving the design you touch, rather than scheduling a big cleanup that never happens.
- Grow the system in **abstractions, not features**: when a feature needs a capability, build a clean, somewhat general abstraction for it, then the feature on top.

## Modifying existing code

1. Ask: given what I know now, what design would I have chosen if this change had been planned from the start? Move the code toward it, within the size of the change the user asked for. If a larger refactor is warranted, propose it and do not start it silently.
2. Do not patch around a problem with flags, special cases or copies. Fix the cause where it lives.
3. Keep comments next to the code they describe and update them in the same change. Put explanations in the code, not only in the commit message. Before finishing, scan the diff for comments the change made wrong.
4. Follow the existing conventions (`obvious-code`), even when you would have chosen differently.

## Designing for performance

- Know roughly what is expensive (network round trips, disk I/O, memory allocation, cache misses) and prefer naturally efficient designs when they are equally simple.
- **Measure before changing** anything for speed, both to find where the time goes and to have a baseline to compare against. Intuition about hot spots is usually wrong.
- When a redesign is needed, design around the **critical path**: find the minimum work the common case needs, and organise the code and data so that path is short. Move special cases off it, ideally behind a single check that sends rare cases elsewhere.
- Simpler code is usually faster code: fewer layers, fewer special cases, fewer checks.

More on the process, development trends (inheritance, agile, TDD, patterns, getters and setters) and performance: [references/process.md](references/process.md).

## Red flags during design

| Red flag | Response |
|---|---|
| Only one design considered | Sketch a second, radically different one |
| Interface comment is long or full of caveats | Simplify the abstraction |
| No short, precise name for the module | It may combine several ideas: split by responsibility |
| Callers of every alternative must do extra work | The module is not doing its job yet: let it absorb that work |
| "We'll clean it up later" | Fix it now, or record a tracked issue with the reason |

## Related skills

- `deep-modules`: judge each alternative (depth, information hiding, layers).
- `error-handling-design`: compare how alternatives handle errors.
- `obvious-code`: write the interface comments well.
- `software-design-guardrails`: the always-on rules and the checker for the resulting code.

## Source

Based on chapters 3 (working code isn't enough), 11 (design it twice), 15 (write the comments first), 16 (modifying existing code), 19 (software trends) and 20 (designing for performance) of *A Philosophy of Software Design* by John Ousterhout (2018). This skill summarises the ideas in its own words and adds an original design-note tool.
