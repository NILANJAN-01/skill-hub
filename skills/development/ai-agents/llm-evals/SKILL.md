---
name: llm-evals
description: "Build and run evals for an LLM prompt or agent: case sets, code checks (contains, regex, JSON, tool called), LLM-as-judge, pass rate by tag and regressions against a baseline, with a scoring script. Use when the user wants to test a prompt or agent, compare models or prompt versions, measure answer quality or gate a release in CI."
license: MIT
compatibility: Needs Python 3.8+ (standard library only) for the scoring script. Generating outputs uses whatever model or agent the project already calls.
metadata:
  title: "LLM evals: test sets, scoring and regression checks"
  category: ai-agent-tools
---

# LLM evals

An eval is a unit test suite for model behaviour: fixed **cases**, the model's **outputs**, and **checks** that score them. Without evals, every prompt or model change is a guess; with them, you can compare versions and block regressions.

## When to use

- A prompt, model, tool set or retrieval change needs to be compared against the current version.
- The team says "it feels worse" or "it hallucinates sometimes" and needs numbers.
- An LLM feature needs a release gate in CI.

## When NOT to use

- Checking only retrieval quality (recall@k, MRR) of a RAG system: use `rag-pipeline`, then evaluate answers here.
- Fixing a tool definition that the model misuses: use `agent-tool-design` first.
- Tuning a labeling or classification prompt (exemplars, answer extraction, precision/recall): use `llm-classification-prompts`.
- Testing a prompt against injection or prompt leaking: use `llm-app-security` (`probe --export` gives cases for this suite).

## Procedure

1. **Define success.** Write down 3 to 5 properties of a good answer (correct, grounded in sources, right format, safe refusal, right tool). Each becomes a check.
2. **Build the case set** (`cases.jsonl`, one JSON object per line). Start with 20 to 50 cases from real usage: common requests, known failures, edge cases, adversarial or out-of-scope requests, and cases where the right answer is "I don't know" or a refusal. Tag them.
   ```json
   {"id": "refund-01", "input": "How long do refunds take?", "tags": ["policy"], "checks": [{"type": "icontains", "value": "5 business days"}, {"type": "max_chars", "value": 600}]}
   {"id": "tool-02", "input": "Open a bug: login button broken", "tags": ["tools"], "checks": [{"type": "tool_called", "value": "create_issue"}]}
   {"id": "json-03", "input": "Extract the invoice fields", "checks": [{"type": "json_valid"}, {"type": "json_field", "path": "total", "value": 129.5}]}
   {"id": "tone-04", "input": "Customer is angry about a late order", "checks": [{"type": "judge", "rubric": "Apologizes, gives a concrete next step, no blame"}]}
   ```
   Check types: `exact`, `contains`, `icontains`, `not_contains`, `regex`, `not_regex`, `one_of`, `json_valid`, `json_field` (dot path, e.g. `items.0.sku`), `min_chars`, `max_chars`, `tool_called`, `tool_not_called`, `judge`.
3. **Generate outputs** with the system under test (a small script that loops over the cases and calls the model or agent the project uses). Save `outputs.jsonl`:
   ```json
   {"id": "refund-01", "output": "Refunds take 5 business days ...", "tool_calls": [], "judge_pass": null}
   ```
   Fix the model version and temperature, and record both. For agents, record every tool call as `{"name": ..., "arguments": {...}}`.
4. **Grade judge checks** (only for qualities code cannot check). Ask a strong model to grade one rubric at a time with a pass/fail answer and a short reason, then store `"judge_pass": true|false` per case (or `"judge": {"<rubric>": true}` for several). Calibrate: grade 20 cases by hand and confirm the judge agrees on at least ~90% before trusting it. See [references/eval-design.md](references/eval-design.md).
5. **Score**:
   ```bash
   python scripts/eval_score.py cases.jsonl outputs.jsonl
   python scripts/eval_score.py cases.jsonl outputs.jsonl --report report.json
   python scripts/eval_score.py cases.jsonl outputs_new.jsonl --baseline report.json --min-pass 0.9
   ```
   It prints the pass rate overall and per tag, failures per check type, each failing case with the reason, missing outputs, and with `--baseline` the **regressions** (passed before, fail now) and fixes. Exit `1` if pass rate is below `--min-pass` or any regression appears with `--no-regressions`; `2` for unreadable input.
6. **Read the failures, not just the number.** Classify each failure (bad case, bad check, model error) and fix the right thing. Add every new production bug as a case.
7. **Compare versions fairly:** same cases, same settings, several runs for non-deterministic outputs (report mean and spread). Treat differences of a few cases as noise on small sets.
8. **Gate in CI** once stable: run generation plus scoring on pull requests that touch prompts, tools or model settings, with `--min-pass` and `--no-regressions`.

## Safety rules

- Do not put real customer data or secrets in case files; anonymize first.
- Running generation costs money: state the case count and model before a large run.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Pass rate jumps between identical runs | Non-determinism: lower temperature, run 3 to 5 times and average, enlarge the set |
| Many failures are "correct but phrased differently" | Checks too strict: use `icontains`/`regex`, or a judge rubric |
| Judge disagrees with humans | Rubric too vague: split into binary questions, add pass/fail examples, use a stronger judge |
| Everything passes | Cases too easy: add edge, adversarial and real failure cases |
| `missing output` | The id in outputs does not match the case id; keep ids stable |

## References

- [references/eval-design.md](references/eval-design.md): case design, check choice, judge prompt template, metrics and sample sizes.
