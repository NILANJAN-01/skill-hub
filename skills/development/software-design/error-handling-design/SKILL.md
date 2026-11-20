---
name: error-handling-design
description: "Design error handling that adds little complexity: define errors out of existence, mask them low, aggregate them into one handler, crash on the unrecoverable, and remove special cases, without hiding errors callers need. Use when writing try/catch, error returns, validation or edge cases, when exception handling spreads through the code, or when an API throws or returns errors too often."
license: MIT. Original summary of ideas from A Philosophy of Software Design by John Ousterhout (2018); no text from the book is reproduced. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Error handling design: define errors out of existence"
  category: software-design-tools
  source: "A Philosophy of Software Design, John Ousterhout, 2018"
  pages: "Chapter 10"
---

# Error handling design

Exceptions, error codes, `null` returns and special-case branches are among the costliest parts of an interface. Throwing is easy, handling is hard. Every error a module reports must be handled by every caller, and sometimes by their callers too. Handlers are hard to write correctly: they may run with half-updated state, they can raise errors of their own, and they rarely execute, so their bugs survive until production. The aim is to **reduce the number of places that must handle errors**, not to detect as many errors as possible.

## When to use

- Writing or reviewing `try/catch`, `except`, `Result`/`Either`, `if err != nil`, error codes or validation.
- An API throws or returns errors for situations callers cannot act on.
- Handlers are copied around, or errors are silently swallowed.
- Code is full of `if` statements for special cases (empty, missing, out of range, "none selected").

## When NOT to use

- Security-relevant validation at a trust boundary (user input, network, files from outside): validate and reject explicitly there. Defining an error away must never accept invalid or malicious input.
- Data-loss and safety-critical paths, where errors must be reported, recorded and possibly retried by design.

## Decision procedure (in order)

For each error or special case, try these techniques in order and stop at the first that fits.

1. **Can the error be defined out of existence?** Change the operation's meaning so that the normal path covers the case:
   - "delete X" becomes "make sure X does not exist", so deleting something already gone succeeds;
   - ranges are clamped, so a slice past the end returns the overlap, possibly empty;
   - "find" returns an empty collection instead of raising "not found" when that is natural for callers;
   - an "unset" state becomes an empty value (an empty selection or list instead of `null` plus flags).
   Do this only when callers really do not need to know. If some caller cares, give it a separate query, so the common path stays clean.
2. **Can it be masked at a low level?** Handle it inside the module so higher layers never see it: retry a transient network error, fall back to a replica, re-create a missing cache entry. Masking belongs in low-level code that many callers share.
3. **Can it be aggregated?** Let many different failures propagate to one handler high up, for example the request loop that turns any request-level error into one error response, using a message built where the error was detected. Use one exception family for "abort this request", distinct from errors that are fatal to the process. Aggregation works best when errors travel several levels before being caught.
4. **Should the program just stop?** For errors that are rare, unrecoverable and signal a bug or a broken environment (out of memory, corrupted internal state, a required resource missing at startup), print a clear diagnostic and exit or abort the operation. Wrap such calls once, for example an allocator that aborts on failure, instead of checking at every call site.
5. **Otherwise, report it,** as precisely as possible, and document it in the interface comment (`obvious-code`): which errors, when, and what the caller should do.

Apply the same thinking to **special cases** in general. Design the normal case so that it handles the special cases without extra branches. An empty range, a zero count or an empty selection should flow through the normal code.

## Rules for writing handlers

- Never swallow an error silently. If ignoring it is correct, write a comment in the handler that says why (`# already deleted: the goal state holds`).
- Do not catch an error just to log it and rethrow at every level. Handle it once, at the level that can act.
- Do not wrap each call in its own handler with the same body. Aggregate.
- Keep cleanup in one place (`finally`, `defer`, `with`/`using`, RAII) instead of repeating it before every early return.
- Make the error message at the point of detection, where the details are known. Let the top-level handler only format and send it.
- Exceptions a module throws are part of its interface. Fewer exceptions make a deeper module.

## Taking it too far

Hide only what callers truly do not need. A network library that discards every failure leaves applications unable to notice lost messages or a dead peer. That information must be exposed, even though it adds complexity. Things that are not important should be hidden; things that are important must be visible.

## Red flags

| Red flag | Fix |
|---|---|
| `except: pass`, `catch (e) {}`, `if err != nil {}` with no comment | Handle, propagate to the aggregate handler, or comment why it is safe |
| The same handler body three times in one file | Let the error propagate to one handler |
| A method that throws for a state that is already its goal (delete missing, close closed) | Redefine the operation's semantics |
| Callers check boundaries before every call | Clamp or accept the edge inside the callee |
| A `null` or "no X" flag tested all over the code | An empty object that the normal code handles |
| Retries scattered across call sites | One retry policy inside the lowest shared layer |
| An exception class per tiny condition | One exception family with descriptive messages, unless callers act differently on each |

Patterns in Python, Java, TypeScript, Go, Kotlin and C#: [references/patterns.md](references/patterns.md).

## Verify

If the `software-design-guardrails` skill is installed, run its checker on the change:

```bash
python <guardrails-skill>/scripts/design_check.py --diff --select swallowed-error,repeated-handler
```

Then check by hand: for each new error path, name the technique you used (define away, mask, aggregate, crash, report). For each one you report, name the caller that can act on it.

## Related skills

- `deep-modules`: masking and defining errors away are ways of pulling complexity down.
- `obvious-code`: document the errors that remain in interface comments.
- `software-design-guardrails`: the always-on rules and the checker.

## Source

Based on chapter 10, "Define Errors Out Of Existence", of *A Philosophy of Software Design* by John Ousterhout (2018). This skill summarises the ideas in its own words with original examples.
