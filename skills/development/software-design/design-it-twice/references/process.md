# Design process notes

Supporting detail for `design-it-twice`, summarised from chapters 3, 11, 15, 16, 19 and 20 of *A Philosophy of Software Design* (Ousterhout, 2018), with original examples.

## Ways to make alternatives genuinely different

| Axis | Option 1 | Option 2 |
|---|---|---|
| Unit of work | One item per call | Batches or ranges per call |
| Who owns the hard part | Caller decides (options, flags) | Module decides (policy inside) |
| Data flow | Push (callbacks, events) | Pull (iterators, queries) |
| State | Stateless functions | An object that remembers context |
| Granularity | Many small operations | A few powerful operations |
| Errors | Reported to the caller | Defined away or masked inside |
| Placement | Library in-process | Separate service |

Pick at least one axis on which the alternatives differ.

## Write the comments first

1. Write the class interface comment: what the abstraction is, in two or three sentences.
2. Write each public method's interface comment and signature, with empty bodies.
3. Read them as a caller would. Are they short and complete? Is anything missing that a caller must know? Does anything describe implementation?
4. Write member comments for the important fields.
5. Fill in the bodies, adding implementation comments for non-obvious blocks as you go.

Comments written after the code tend to describe the code. Comments written first describe the abstraction and expose design problems while they are still cheap to fix.

## Development trends, viewed through complexity

| Practice | Helps when | Hurts when |
|---|---|---|
| Interface inheritance | Many implementations share one interface (readers learn it once) | It is used for a single implementation, as ceremony |
| Implementation inheritance | It removes real duplication | Subclasses depend on parent internals (information leakage). Prefer composition |
| Agile, incremental delivery | Increments are clean abstractions | Increments are thin features hacked onto whatever exists (tactical) |
| Unit tests | They give the safety net that makes refactoring cheap | They pin implementation details and block redesign |
| Test-driven development | Writing a failing test before a bug fix | It focuses on making the next test pass instead of finding the best design |
| Design patterns | The pattern fits the problem exactly | It is applied because patterns are "good" and adds layers that hide nothing |
| Getters and setters | Rarely: they expose internal state | Usually: shallow methods that leak representation. Offer real operations instead |

## Performance

1. **Know the costs.** Network round trips (within a data centre: tens of microseconds and up), disk and SSD I/O, dynamic memory allocation and cache misses dominate. Measure unfamiliar operations with micro-benchmarks.
2. **Prefer the naturally efficient option when it is just as simple,** for example a hash map instead of a linear scan of a list for lookups.
3. **Measure first.** Profile the real workload, find where time goes, keep the numbers as a baseline, and re-measure after each change. Revert changes that do not help.
4. **Critical-path redesign** (the last resort, for code that must be fast):
   - Imagine the shortest code that could handle the common case if there were no special cases and you could choose any data structures.
   - Reshape the real code toward that ideal.
   - Test for all special cases with one check at the start, and branch to separate slower code when one applies.
   - Remove layers on the hot path when each adds only a call.
5. Clean design and speed usually agree: deep modules do more per call, and fewer special cases mean fewer branches.

## Original worked example (sketch)

Designing a "recently viewed products" feature:

- **A, per-event:** `record_view(user, product)` writes each view; `recent(user, n)` queries the latest. Simple, but writes on every page view, and each caller must deduplicate.
- **B, session buffer:** an in-memory buffer per session, flushed on logout or timeout; `recent(user)` merges the buffer with storage. Fewer writes, but views are lost if the process crashes before a flush.
- **C, bounded list owned by one module:** `RecentlyViewed.add(user, product)` keeps at most 20 distinct items per user, newest first, and deduplicates inside. Callers never deal with duplicates or limits.

C hides the deduplication and the bound (knowledge that would otherwise leak into every caller). B's batching can later be an implementation detail inside C. Decision: C's interface, with A's storage, and B's batching kept as an optimisation to add if measurements show write load matters.
