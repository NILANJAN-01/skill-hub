---
name: obvious-code
description: "Write code a first-time reader understands: interface comments and docstrings that add what the code cannot say, implementation comments that explain what and why, precise and consistent names, following the project's conventions, and avoiding nonobvious constructs. Use when writing or reviewing comments, docstrings, Javadoc, JSDoc or KDoc, naming things, or when code is hard to read or comments are useless or stale."
license: MIT. Original summary of ideas from A Philosophy of Software Design by John Ousterhout (2018); no text from the book is reproduced. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Obvious code: comments, names and consistency"
  category: software-design-tools
  source: "A Philosophy of Software Design, John Ousterhout, 2018"
  pages: "Chapters 12-14, 16-18"
---

# Obvious code

Code is **obvious** when a reader can skim it and their first guess about what it does is correct. Obscurity, meaning important information that is not visible, is one of the two causes of complexity. You can remove it in three ways, in order of preference: need less information (a simpler design), reuse what readers already know (conventions), or show the information where it is needed (names and comments). "Obvious" is judged by a first-time reader, not by the author. If a reviewer finds something confusing, it is confusing.

## When to use

- Writing or reviewing comments, docstrings, Javadoc, JSDoc, KDoc, Go doc comments or C# XML docs.
- Naming variables, functions, classes, files and modules.
- Code is hard to read, comments are useless or out of date, or names cause misunderstandings.
- Working in an unfamiliar file or project and deciding how new code should look.

## When NOT to use

- The real problem is the design (a hard-to-describe module, a tangled interface): use `deep-modules` first. A comment cannot rescue a bad abstraction.
- Pure formatting (indentation, line length): use the project's formatter.

## Comments: what to write

Comments record what the code cannot express: intent, abstractions, rationale, units, bounds, invariants, ownership and ordering rules. A good comment works at a **different level of detail** from the code. It is either more precise (exact meaning of a value) or more abstract (what a block achieves). A comment at the same level as the code just repeats it.

| Kind | Where | Contents |
|---|---|---|
| **Interface comment** | Before every class and every non-trivial function or method | For a class: the abstraction it provides, what an instance represents, its limits (for example "not thread-safe"). For a function: its behaviour as callers see it, each argument (meaning, units, allowed range, ownership), the result, side effects, errors, preconditions. No implementation detail |
| **Member comment** | Next to each field or important variable | What it *represents*, not how it changes: units, inclusive or exclusive bounds, what `null` or empty means, invariants, who frees or closes it |
| **Implementation comment** | Inside functions, before a block or loop | *What* the block achieves and *why*: tricky reasons, bug references, non-obvious ordering. Short functions usually need none |
| **Cross-module comment** | Where a maintainer will look: the declaration they must change, or one central design-notes file that the code points to | A decision that spans modules: "adding a status code also requires X and Y" |

Interface comments are written **before** the code (`design-it-twice`). If a complete interface comment is long or hard to write, the design is probably wrong.

## Procedure: write or review a comment

1. Pick the project's convention (docstring style, Javadoc tags) and follow it. Templates per language: [references/comment-templates.md](references/comment-templates.md).
2. Use different words from the name. "Gets the user name" on `getUserName` adds nothing. Ask: could someone write this comment just by reading the line next to it? If so, rewrite it or delete it.
3. For variables, think nouns: what the value *means* ("number of bytes already sent to the client"), not the code that sets it.
4. For interface comments, describe only what callers need. Move how-it-works text into the body.
5. For implementation comments, describe what a block achieves and why it is needed, at a higher level than the statements.
6. Keep comments next to the code they describe, so they get updated together. Put a decision's rationale in the code, not only in the commit message. Do not duplicate documentation; point to the one place that holds it.
7. Before finishing, read your diff and update every comment the change made wrong.

## Names

- **Precise.** A name should create an accurate image of the thing, and rule out what it is not. `count` (of what?), `data`, `info`, `tmp`, `status`, `result` in a function that returns nothing, and `a`/`b` for two prices are vague. Use `activeSessionCount`, `retryDeadline`, `netPrice`. Short names such as `i` are fine when the whole scope fits on screen.
- **Booleans are predicates:** `isMuted`, `hasPaid`, `retryAllowed`, not `soundStatus` or `flag`.
- **Not too specific either:** a general `send(message)` should not call its parameter `welcomeEmail` if it sends any message.
- **Consistent:** one name for one concept everywhere, never the same name for two different concepts (`id` meaning both a user id and an account id invites bugs). Use distinct names: `userId`, `accountId`.
- **Hard to name?** If no short precise name exists, the entity probably does more than one thing. Revisit the design.

Naming checklist with examples: [references/naming.md](references/naming.md).

## Consistency

- When working in existing code, find how it already does similar things (naming, structure, error style, file layout) and do the same. The value of consistency is usually greater than the value of your preferred style.
- Do not introduce a "better" convention piecemeal. Change a convention only if there is new information that justifies it and the old uses are all updated, with the team's agreement.
- Consistent means similar things look alike *and* different things look different. Do not force unlike things into one pattern or one name.
- Automate conventions where possible (formatters, linters, the checker in `software-design-guardrails`). Tools work better than reminders.

## Things that make code less obvious

| Construct | Remedy |
|---|---|
| Generic containers (`Pair`, `Tuple`, a 3-tuple return) | A small named type whose fields say what each value means |
| Behaviour that surprises (a constructor that starts threads, a getter that writes) | Avoid it; if unavoidable, say so in the interface comment and where readers will look |
| Event-driven callbacks | Interface comment on each handler saying when and on which thread it runs |
| Declared type differs from the created type | Prefer the type that matches the behaviour readers rely on; say why if they differ |
| Dense code without visual structure | Blank lines between logical blocks, each block headed by a short "what" comment |

Write code for ease of reading, not ease of writing: a few extra minutes for the writer save every future reader.

## Verify

With the `software-design-guardrails` skill installed:

```bash
python <guardrails-skill>/scripts/design_check.py --diff --fail-on info \
  --select comment-repeats-code,doc-repeats-name,missing-interface-doc,impl-in-interface-doc,vague-name,non-predicate-boolean,generic-container
```

Then read the diff as a stranger would. Mark every place where you would have to read another file to understand a line; each one needs a better name, a comment or a simpler design.

## Related skills

- `deep-modules`: when a comment is hard to write, fix the abstraction.
- `design-it-twice`: write interface comments first, as a design tool.
- `software-design-guardrails`: the always-on rules and the checker.
- `professional-writing`: READMEs and longer technical documentation.

## Source

Based on chapters 12 to 14 and 16 to 18 of *A Philosophy of Software Design* by John Ousterhout (2018): why write comments; comments should describe things that are not obvious from the code; choosing names; modifying existing code; consistency; code should be obvious. This skill summarises the ideas in its own words with original examples.
