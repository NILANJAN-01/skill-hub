---
name: llm-classification-prompts
description: "Build and tune an LLM prompt that labels or classifies text (sentiment, intent, moderation, triage, yes/no): pick few-shot exemplars, run prompt variants through any model command, extract answers, and score precision, recall and F1 with a bundled script. Use when the user wants to classify or label data with an LLM, or a labeling prompt gives wrong, unparsable or inconsistent answers."
license: "CC-BY-4.0. Method from The Prompt Report (Schulhoff et al., 2024, arXiv:2406.06608, CC BY 4.0), section 6.2; scripts MIT. See THIRD_PARTY_NOTICES.md"
metadata:
  title: "LLM classification prompts: build, run, score"
  category: ai-agent-tools
  source: "The Prompt Report: A Systematic Survey of Prompt Engineering Techniques, Schulhoff et al., arXiv:2406.06608v6, 2025"
  pages: "Sections 2.2.1, 2.5, 6.2, A.7"
---

# LLM classification prompts

`scripts/prompt_bench.py` runs the loop that works for labeling prompts: build variants, run them on labeled data, score them, read the errors, change one thing. It works with any model, because it sends each prompt to a command you choose (prompt on stdin, answer on stdout). It needs only Python 3.8+ and prints a short score table, so the agent reads results, not raw outputs.

## When to use

- Classifying or labeling text with an LLM: sentiment, intent, topic, moderation, ticket triage, yes/no questions.
- A labeling prompt returns sentences instead of labels, wrong labels, or different answers per run.
- Comparing zero-shot, few-shot, chain-of-thought, exemplar choices or models on the same labeled data.

## When NOT to use

- Free-form outputs (summaries, code, chat answers) or agent behaviour: use `llm-evals`.
- Writing a one-off prompt without labeled data: use `prompt-engineering`.
- More than a few thousand items, or a training budget: a fine-tuned classifier is usually cheaper.

## Safety rules for the agent

- Ask before sending the user's data to a hosted model, and don't put personal data in exemplars or context; replace names and emails.
- Keep a held-out test set that is never used for exemplars or tuning, and report its score separately. Dev-set gains often shrink on test.
- Ask the domain owner which error is worse (missed positives or false alarms). F1 weighs them equally; on safety tasks recall usually matters more.
- `run` calls a model once per prompt and sample: tell the user the call count (items × variants × samples) before large runs.

## Procedure

Paths are relative to this skill's folder. Data is JSON Lines: `{"id": 1, "input": "...", "label": "yes"}`.

1. **Split the data**: about 30-50% for exemplars and development (`dev.jsonl`), the rest for test (`test.jsonl`). Check the label balance.
2. **Write the template** with `{EXEMPLARS}` and `{INPUT}`. Give the task definition, the allowed labels and the exact output form ("Answer with one word: Yes or No"). Lint it with `prompt-engineering`'s `prompt_lint.py`.
3. **Build a baseline** (zero-shot), then few-shot variants:
   ```bash
   python scripts/prompt_bench.py build --template t.txt --data dev.jsonl --out p0.jsonl
   python scripts/prompt_bench.py build --template t.txt --data dev.jsonl --exemplars dev.jsonl --k 8 \
       --select balanced --orders 3 --out p8.jsonl
   ```
   `--select balanced|random|similar|first`; `similar` picks the nearest exemplars per input. Items used as exemplars are never tested on. `--orders N` makes N exemplar orders, so you can see the order sensitivity.
4. **Run** through a model command (it can resume: rerun the same line after a failure):
   ```bash
   python scripts/prompt_bench.py run p8.jsonl --cmd "ollama run llama3.2" --jobs 4 --out o8.jsonl
   ```
   Any CLI or script that reads stdin works. Add `--samples 5` (with a temperature around 0.5 in the command) for self-consistency voting.
5. **Score** and compare extractors:
   ```bash
   python scripts/prompt_bench.py score o8.jsonl --labels yes,no --positive yes --compare
   python scripts/prompt_bench.py score o8.jsonl --labels yes,no --positive yes --vote      # ensemble orders
   python scripts/prompt_bench.py score o8.jsonl --labels yes,no --against o0.jsonl         # fixed/broken items
   ```
   After reasoning, use `--extract last`. Use `--map map.json` (`{"no": ["not entrapment"]}`) when the model answers in words. A high unparsed rate means you should fix the prompt; an extraction prompt can hide wrong answers.
6. **Read the errors and add reasoning exemplars (AutoDiCoT)**: ask the model why it was right, or tell it the correct label and ask why, then reuse the explanations as exemplars:
   ```bash
   python scripts/prompt_bench.py autodicot o8.jsonl --labels yes,no --out f.jsonl
   python scripts/prompt_bench.py run f.jsonl --cmd "..." --out fo.jsonl
   python scripts/prompt_bench.py autodicot --merge fo.jsonl --out reasoned.jsonl   # review, then --exemplars reasoned.jsonl
   ```
7. **Pick the best variant on dev, then score it once on test.** Report the test precision, recall, F1 and unparsed rate, plus the spread across orders or runs.

More detail and the case-study numbers: [references/workflow.md](references/workflow.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Unparsed rate high (`exact` much worse than `last`) | Restate the output form; put "Answer:" last in the template; use `--extract last` or `--map` |
| Model gives advice or refuses instead of a label | Make the task explicit ("Is this X? Yes or No."); sensitive domains may need another model |
| Accuracy differs a lot between `--orders` | Order sensitivity: `--vote` across orders, or more and balanced exemplars |
| Everything predicted as one label | Balance exemplars (`--select balanced`), check the last exemplars' labels, state both labels |
| Dev score rose, test score fell | Overfitting to dev: fewer hand tweaks, larger dev set, keep the variant that is best on average |
| `exit 1: ...` from `run` | The model command failed; run it by hand: `echo hi \| <cmd>` |
