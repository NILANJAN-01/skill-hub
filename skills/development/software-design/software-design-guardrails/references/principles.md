# The design principles, in brief

Paraphrased from the summary of principles in *A Philosophy of Software Design* (Ousterhout, 2018). Chapter numbers point to the full reasoning in the book.

| # | Principle | What it means for an agent writing code | Chapter |
|---|---|---|---|
| 1 | Complexity is incremental | No change is too small to matter. Do not accept "just one" extra dependency or obscurity | 2 |
| 2 | Working code is not enough | Passing tests is the minimum. The structure must also stay easy to change | 3 |
| 3 | Invest a little all the time | Spend some of every task (the book suggests about 10-20%) improving the design you touch | 3 |
| 4 | Modules should be deep | The interface should be much simpler than what it hides | 4 |
| 5 | Make the common case simple | Design the interface around its most frequent use; rare features must not burden it | 4, 5 |
| 6 | A simple interface beats a simple implementation | When complexity is unavoidable, the module absorbs it so callers do not | 8 |
| 7 | General-purpose modules are deeper | Interfaces that are somewhat general are usually simpler and hide more | 6 |
| 8 | Separate general-purpose and special-purpose code | Mechanisms stay general; specific uses live above them | 9 |
| 9 | Different layers, different abstractions | If two adjacent layers look alike, one of them is probably not earning its place | 7 |
| 10 | Pull complexity downward | The module's developers suffer so its many users do not | 8 |
| 11 | Define errors and special cases out of existence | Choose semantics where the normal path covers the unusual case | 10 |
| 12 | Design it twice | Compare at least two different designs before committing to one | 11 |
| 13 | Comments describe what is not obvious from the code | Intent, rationale, units, invariants and abstractions, never a restatement | 13 |
| 14 | Design for ease of reading, not ease of writing | Spend writer time to save reader time | 18 |
| 15 | Increments should be abstractions, not features | Grow the system by adding clean abstractions, then build features on them | 19 |

## The two causes of complexity

- **Dependencies**: code that cannot be understood or changed in isolation. Some are necessary. Keep them few, simple and visible (an explicit API rather than a shared hidden assumption).
- **Obscurity**: important information is not obvious, for example a generic name, undocumented units or a hidden dependency. The best cure is a simpler design. The next best is a precise comment.

## Mindset

- *Tactical* programming optimises for finishing this task now. Each shortcut seems small, but they accumulate until every change is slow.
- *Strategic* programming treats a great design as the primary goal; working code is a by-product. Invest continually: fix design problems when you find them instead of patching around them.
