## Software design rules (apply to every code change)

Goal: every change leaves the system simpler to understand and change. Working code is not enough.

**Before writing code**
- Look at how this project already does similar things (names, layout, error style) and do it the same way.
- New module, class or public API: sketch two genuinely different interfaces, pick the one that is simplest for callers, and write its interface comment before the body.

**While writing code**
1. Deep modules: a small, simple interface hiding a lot. Add a class, function, parameter or layer only if it hides something real.
2. No pass-through methods or pass-through variables. Each layer offers a different abstraction from the one below it.
3. Hide each design decision (format, protocol, data layout) in one module. Do not split code by execution order (read, then parse, then write) when the steps share knowledge.
4. Make the common case simple: sensible defaults, no option or config knob unless callers really know better.
5. Pull complexity down: the module handles the hard parts instead of pushing them to every caller.
6. Keep general-purpose mechanisms free of special-purpose code; put special cases at the edges.
7. Errors: first define them out of existence (idempotent operations, clamped ranges, empty results), then mask low, aggregate into one handler, or crash on the unrecoverable. Never swallow an error silently.
8. Comments: every class and public function gets an interface comment (what it does for callers, each argument with units and bounds, the result, side effects, errors, preconditions). Inside the code, explain what and why, never repeat the code. Keep interface comments free of implementation detail.
9. Names: precise and consistent; booleans read as predicates. Avoid data, info, tmp, obj, result-for-nothing, manager, helper. A thing that is hard to name or describe signals a design problem.
10. Obvious code: return named types instead of generic pairs or tuples; no surprising behaviour without a comment. Split or join functions by abstraction, never by line count.
11. Strategic, not tactical: when you touch a design problem, fix it in the same change instead of patching around it; update comments in the same change.
12. Performance: measure before optimising; keep special cases off the critical path.

**Before finishing**
- Run `{check}` and fix each finding, or justify it in the code with `design-check: ignore[<rule>] -- <reason>`.
- Review the diff for the red flags the script cannot see: information leakage, temporal decomposition, conjoined methods, special-general mixture, hard-to-describe interfaces.
- In the summary, name any design debt you deliberately left, and why.
