---
name: deep-modules
description: "Design deep modules, classes, functions and APIs: simple interfaces that hide a lot. Covers information hiding and leakage, temporal decomposition, general vs special-purpose code, pass-through methods and variables, defaults vs config knobs, and when to split or merge. Use when designing or refactoring a class, module, service or API, or when code is over-abstracted, tangled or full of tiny wrappers."
license: MIT. Original summary of ideas from A Philosophy of Software Design by John Ousterhout (2018); no text from the book is reproduced. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Deep modules: interfaces, information hiding, layers"
  category: software-design-tools
  source: "A Philosophy of Software Design, John Ousterhout, 2018"
  pages: "Chapters 4-9"
---

# Deep modules

A *module* is anything with an interface and an implementation: a function, a class, a package, a service. Its **interface** is everything a caller must know to use it. That includes the signature, and also the informal parts: behaviour, side effects, ordering rules, error cases. The **cost** of a module is its interface. The **benefit** is the functionality it hides. A **deep** module gives a lot of functionality behind a small interface. A **shallow** module makes callers learn nearly as much as it saves them.

Prefer a few deep modules to many shallow ones. Splitting code into ever smaller pieces does not reduce complexity; every new interface adds some.

## When to use

- Designing a new class, module, package, service or public API.
- Refactoring code that has many tiny classes, wrapper methods or "manager/helper" layers.
- A change keeps touching many files (change amplification), or two modules always change together.
- Deciding whether to split a long function or class, or to merge small ones.
- Reviewing a design for the red flags below.

## When NOT to use

- Error and edge-case design: use `error-handling-design`.
- Names, comments and readability: use `obvious-code`.
- Comparing whole alternative designs before coding: use `design-it-twice` (then come back here to judge each one).

## Procedure: design or review a module

1. **List what the module knows.** Write down the design decisions it owns: data layout, file or wire format, algorithm, policy, ordering rules, retry and caching behaviour. A module that owns no decision is shallow.
2. **Check that each decision lives in one place.** If a format or rule is also known elsewhere, that is *information leakage*. Either merge the modules that share it, or pull the knowledge into one module behind an interface that does not expose it.
3. **Split by knowledge, not by time.** If the modules are named after phases (`Reader`, `Transformer`, `Writer`) and two phases share a format, that is *temporal decomposition*. Make one module own the format and serve every phase that needs it.
4. **Sketch the interface for the common case.** Write the two or three calls a typical caller makes. Everything else (rare options, tuning, alternative modes) goes behind defaults or separate methods, so most callers never see it.
5. **Measure depth.** Compare what a caller must learn with what the module does for them. Danger signs: the interface comment would be longer than the code; the method only calls another method; callers must call several methods in a fixed order; callers must handle states the module could have handled.
6. **Make it somewhat general-purpose.** Implement only today's needs, but shape the interface so it is not tied to today's single caller. Ask: what is the simplest interface that covers all current needs? In how many situations will this method be used? Is it still easy to use for the current need? A method that only makes sense for one caller (`deleteSelectedRowFromGrid`) usually belongs in that caller, built on a general method (`delete(range)`).
7. **Pull complexity down.** When something is unavoidably hard (retries, caching, conversions, partial failures), handle it inside the module rather than exporting it as an exception, a flag or a configuration parameter. Add a configuration knob only when callers really know better than the module, and give it a computed default.
8. **Check the layers.** Each layer should offer a different abstraction from the one below. Look for pass-through methods, wrapper classes that copy an interface, and parameters threaded through layers that never use them (see below).
9. **Verify** with the checker from `software-design-guardrails` if it is installed (`design_check.py --diff --select pass-through-method,pass-through-variable,single-use-shallow,trivial-accessor,long-parameter-list,duplicate-code`), then review the red flags by hand.

## Decision guide: together or apart?

Bring code together when the pieces:
- share information (both depend on the same format, protocol or invariant);
- are always used together, in both directions (each user of A also uses B, and the other way round);
- fall under one simple higher-level concept;
- cannot be understood without reading each other;
- would get a simpler interface, or lose duplicated code, by merging.

Keep code apart when:
- one piece is a general mechanism and the other a particular use of it (keep the mechanism general; move the special use up a layer);
- the pieces are truly independent, so a reader can study one without the other.

For **functions**, length alone is never a reason to split. Split when a *subtask* can be pulled out that a reader can understand without the parent, and the parent without the child's body. Or split when one function does two unrelated things and callers usually need only one of them. Do not split if callers would have to call the pieces in sequence and pass state between them. Merge when two functions can only be understood together (*conjoined methods*), or when merging removes an interface or duplicated code.

## Pass-throughs and how to remove them

| Problem | Fix options |
|---|---|
| **Pass-through method**: the method only forwards to another object's method with the same or a similar signature | Let callers use the lower object directly; move the responsibility so each class owns a distinct set; or merge the two classes |
| **Decorator / wrapper class** for a small feature | Add the feature to the base class if most users want it; merge it with the one use that needs it; merge it into an existing wrapper; or make it a standalone class that does not wrap |
| **Pass-through variable**: a value travels down through methods that do not use it | Store it in an object both ends already share; or create a *context object* for process-wide state, keep a reference in long-lived objects, and pass it only to constructors. Keep context fields immutable where possible |

Interface duplication is fine when each method adds real work: a *dispatcher* chooses which method to call, and several implementations of one interface (drivers, strategies) let readers learn the interface once.

## Red flags

| Red flag | Looks like |
|---|---|
| Shallow module | One-line methods, getters and setters for every field, classes that wrap one call |
| Classitis | Many tiny classes, each with its own interface and boilerplate, that are always used together |
| Information leakage | Two modules both parse, build or assume the same format |
| Temporal decomposition | `FileReader` + `FileParser` + `FileWriter` that all know the file format |
| Overexposure | The common call needs flags or objects that only matter in rare cases |
| Pass-through method / variable | `def save(self, x): return self.repo.save(x)`; `config` passed through five functions to reach one |
| Special-general mixture | A generic undo stack that knows about the text editor's selection |
| Repetition | The same block pasted in several places |
| Conjoined methods | Reading `parse_header` requires reading `parse_body` |

Worked before/after examples in Python, TypeScript and Java: [references/examples.md](references/examples.md).

## Taking it too far

- Hide only what callers do not need. If performance tuning really differs per caller, the parameter belongs in the interface.
- Pulling complexity down makes sense when it is related to the module's job, simplifies many callers, and simplifies the interface. Pushing unrelated features into a class just leaks information the other way.
- A single giant class is not deep; it is a pile. Depth is about a *simple interface for a coherent idea*.

## Related skills

- `software-design-guardrails`: always-on rules and the checker.
- `design-it-twice`: compare whole alternatives before committing.
- `error-handling-design`: exceptions are part of the interface, and often the costliest part.
- `obvious-code`: interface comments define the abstraction; if one is hard to write, revisit the design here.

## Source

Based on chapters 4 to 9 of *A Philosophy of Software Design* by John Ousterhout (2018): modules should be deep; information hiding and leakage; general-purpose modules are deeper; different layer, different abstraction; pull complexity downwards; better together or better apart. This skill summarises those ideas in its own words with original examples.
