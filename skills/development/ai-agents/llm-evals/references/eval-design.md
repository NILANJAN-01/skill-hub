# Eval design notes

## Case mix (starting point)

| Share | Kind | Example |
|---|---|---|
| ~50% | Common real requests | Taken from logs or support tickets (anonymized) |
| ~20% | Known failures | Every bug report becomes a case |
| ~15% | Edge cases | Empty input, very long input, other languages, ambiguous wording |
| ~15% | Should refuse / say "don't know" / not use a tool | Out-of-scope or unanswerable questions, prompt injection attempts |

Keep a frozen **test** set for decisions and a separate **dev** set you look at while tuning prompts, so you do not overfit.

## Choosing checks

Prefer the cheapest check that captures the property:

1. **Code checks** (exact, contains, regex, JSON fields, length, tool called): fast, free, deterministic.
2. **Reference comparison**: compare to a gold answer (contains key facts; for extraction, compare fields).
3. **LLM-as-judge**: tone, helpfulness, faithfulness to sources, completeness. Use only when 1 and 2 cannot work.

For agents also check: the right tool was called, with valid arguments, in a reasonable number of steps, and destructive tools were not called without confirmation.

## Judge prompt template

```
You are grading one answer against one criterion.

Criterion: {rubric}

Question:
{input}

Reference material (may be empty):
{context}

Answer to grade:
{output}

Think briefly, then reply with JSON only: {"reason": "<one sentence>", "pass": true|false}
```

Rules: one criterion per call; binary pass/fail rather than 1-10 scores; give the judge the sources when grading faithfulness; randomize order when comparing two answers pairwise (position bias); use a model at least as strong as the one being graded.

## Metrics

- **Pass rate** per check and per tag; overall pass rate = cases where every check passed.
- **Regressions**: cases that passed in the baseline and fail now. Often more useful than the average.
- For classification-style outputs: precision and recall per class.
- For RAG answers: faithfulness (claims supported by retrieved text) and answer relevance; retrieval itself is measured with recall@k and MRR in `rag-pipeline`.
- Track cost and latency per case next to quality.

## How many cases

With n cases, a pass rate's 95% margin of error is roughly `1 / sqrt(n)`: about ±14 points at 50 cases, ±7 at 200, ±3 at 1000. Small sets show large regressions only; do not celebrate a 2-point gain on 50 cases.

## Output record format used by eval_score.py

```json
{"id": "case-id", "output": "text the model returned", "tool_calls": [{"name": "create_issue", "arguments": {"title": "..."}}],
 "judge_pass": true, "judge": {"Apologizes, gives a concrete next step": true}}
```
`output` may also be named `response` or `completion`. `judge_pass` applies to every `judge` check of the case; `judge` maps a rubric to its result when there are several. A judge check with no result is reported as **pending**, not failed.
