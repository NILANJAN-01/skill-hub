# Red flags: symptoms, checks and fixes

A red flag is a symptom that suggests a design problem. It is not proof: look at the code, then decide. *Checker* names the `design_check.py` rule that can spot it. *Skill* names the skill in this set that explains the fix in depth. Chapters refer to *A Philosophy of Software Design* (Ousterhout, 2018).

| Red flag | Symptom | Checker | Fix | Skill |
|---|---|---|---|---|
| Shallow module (ch. 4) | The interface is about as complex as the implementation: a one-line function, a class that wraps one call, a getter for every field | `single-use-shallow`, `trivial-accessor` | Merge it into its caller or its neighbour, or give it enough work to hide something | deep-modules |
| Information leakage (ch. 5) | One design decision (a format, a protocol, a magic constant, an ordering rule) is known in two or more places | review | Put the knowledge in one module. Merge the modules that share it, or extract it behind a simple interface | deep-modules |
| Temporal decomposition (ch. 5) | Modules follow execution order (reader, processor, writer) and share knowledge because of it | review | Split by knowledge, not by time: one module per piece of knowledge, used at every stage that needs it | deep-modules |
| Overexposure (ch. 5) | The common use requires learning rare options; long parameter lists; required arguments the module could work out itself | `long-parameter-list` | Defaults for the common case; rare options behind separate methods; let the module decide | deep-modules |
| Pass-through method (ch. 7) | A method only calls another method with the same or a similar signature | `pass-through-method` | Expose the lower object, redistribute responsibilities, or merge the classes | deep-modules |
| Pass-through variable (ch. 7) | A value is passed down through layers that do not use it | `pass-through-variable` | A shared object both ends already have, or a context object stored in long-lived objects | deep-modules |
| Repetition (ch. 9) | The same or nearly the same code appears more than once | `duplicate-code`, `repeated-handler` | Find the missing abstraction: one function with a simple signature, or restructure so the code runs once | deep-modules |
| Special-general mixture (ch. 9) | A general mechanism contains code for one particular use | review | Keep the mechanism general. Move the special case up into the code that needs it | deep-modules |
| Conjoined methods (ch. 9) | You cannot understand one method without reading another | review | Rejoin them, or split along a cleaner line so each can be read alone | deep-modules |
| Too many exceptions (ch. 10) | Callers wrap calls in handlers for cases they cannot act on | `swallowed-error`, `repeated-handler` | Define the error away, mask it low, aggregate it high, or crash | error-handling-design |
| Comment repeats code (ch. 13) | The comment says what the next line already says, or reuses the words of the name | `comment-repeats-code`, `doc-repeats-name` | Write what the code cannot say: why, units, bounds, invariants, intent. Or delete the comment | obvious-code |
| Implementation documentation contaminates interface (ch. 13) | The interface comment explains how it works | `impl-in-interface-doc` | Move how-it-works text into the body; keep what callers need | obvious-code |
| Vague name (ch. 14) | The name could mean many things: `data`, `info`, `tmp`, `count`, `status` | `vague-name`, `non-predicate-boolean` | A precise name that creates an image of what the thing is and is not | obvious-code |
| Hard to pick name (ch. 14) | No short precise name exists | review | The entity may mix several ideas: redesign it so it has one clear purpose | obvious-code |
| Hard to describe (ch. 15) | A complete interface comment must be long and full of caveats | review | Simplify the abstraction until a short, complete comment is possible | design-it-twice |
| Nonobvious code (ch. 18) | A first-time reader cannot guess the behaviour correctly: generic containers, surprising side effects, hidden threads | `generic-container` | Named result types, conventional behaviour, a comment where surprise is unavoidable | obvious-code |
| Tactical shortcut (ch. 3) | A kludge marked "temporary", "for now", HACK, XXX | `tactical-marker` | Fix it in this change, or file a tracked issue and reference it | design-it-twice |

## Self-review checklist (run on every diff)

- [ ] Every new class, function, parameter and layer hides something; none just forwards.
- [ ] Each design decision lives in one module; nothing is split by execution order.
- [ ] The common case needs no options; defaults are sensible.
- [ ] Errors are defined away where possible; nothing is swallowed without a comment.
- [ ] Every new public class and function has an interface comment that adds information.
- [ ] Names are precise and follow the project's conventions; booleans read as predicates.
- [ ] Comments changed together with the code they describe.
- [ ] No duplicated blocks; no generic pair or tuple results.
- [ ] Any shortcut left behind is named in the summary with a reason.
