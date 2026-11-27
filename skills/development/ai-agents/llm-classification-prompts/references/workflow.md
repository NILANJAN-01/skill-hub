# Labeling-prompt workflow: details and evidence

Based on section 6.2 and appendix A.7 of *The Prompt Report* (Schulhoff et al., 2024, arXiv:2406.06608, CC BY 4.0),
summarised in our own words, plus usage notes for `prompt_bench.py`.

## The case study in brief

An expert prompt engineer labelled Reddit posts for *entrapment* (a key warning sign of suicidal crisis) with
GPT-4-class models: 121 development posts and 100 test posts, 47 recorded steps, about 20 hours.

| Step | Dev F1 | Note |
|---|---|---|
| Zero-shot + definition, exact "Yes"/"No" match | low | many outputs not parsable |
| Same, match the first characters instead | 0.40 (R 1.0, P 0.25) | the extractor alone changed the score |
| 10-shot + definition | 0.45 | |
| 1-shot AutoDiCoT + project email + "only explicit" rule | 0.36 | led to the best prompt later |
| Email removed | 0.18 | context mattered a lot |
| 10-shot AutoDiCoT | **0.53** (R 0.86, P 0.38) | best manual prompt |
| 20-shot AutoDiCoT | 0.49 | more exemplars were worse, on test too |
| Extraction prompt added | 0.48 | accuracy up, F1 down: unparsed outputs were often wrong |
| 3 exemplar orders, ensembled | 0.36 | other orders broke the output format |
| Email anonymised | 0.45 | unexplained sensitivity |
| DSPy automatic optimisation | test 0.548 | beat the manual prompts on test |

Lessons that carry over:

- **The extractor is part of the prompt.** Measure the unparsed rate and compare extractors (`score --compare`).
- **Effects can be inexplicable.** An accidental duplicated paragraph helped; removing it hurt. Only data tells.
- **Check the goal with the domain expert.** The "only label explicit statements" rule raised F1 but contradicted
  the clinicians, who said entrapment is often implicit and that recall matters most.
- **Guardrails can block the task.** The model gave mental-health advice instead of labels until the task was made
  explicit and the model was changed.
- **Automation plus human review worked best.** An automatic optimiser (DSPy) found a better prompt; humans then
  adjusted it.

## AutoDiCoT (Automatic Directed Chain-of-Thought)

For each development item: label it with the current prompt. If the label is right, ask "Why?"; if wrong, say
"It is actually [label], please explain why." Keep (input, explanation, label) triples and use them as
Q/R/A exemplars. It mixes automatic CoT generation with showing the model which reasoning to follow (like
contrastive CoT). Explanations are plausible stories, not the model's real process: read them and drop wrong ones.

`prompt_bench.py` does this in three commands (`autodicot`, `run`, `autodicot --merge`); `build` switches to the
`Q/R/A` exemplar format when every exemplar has a `reasoning` field.

## Few-shot choices to test

| Choice | Options in `build` | Evidence |
|---|---|---|
| How many | `--k 0, 4, 8, 16` | more usually helps, flattening near 20; in the case study 20 was worse than 10 |
| Which | `--select balanced / random / similar` | similar exemplars usually help; balanced labels avoid bias |
| Order | `--orders 3`, then `score` shows the spread, `--vote` ensembles | order alone can swing accuracy widely |
| Format | `--format "Input: {input}\nLabel: {label}"` | try 2-3 formats; full words vs Q/A changed parse rates |

## Scoring notes

- `accuracy` counts unparsed outputs as wrong unless `--default LABEL` fills them (the case study's "default to
  reject" did not help).
- With `--samples N`, each prompt's outputs are majority-voted (self-consistency); ties go to the earliest answer.
- With several `--orders`, `score` reports accuracy per order and its spread; `--vote` votes across orders instead.
- `--against old.jsonl` lists item ids a change fixed and broke. Read both lists before keeping a change.
- `--json` gives everything (per-label precision/recall/F1, confusion matrix, first errors) for reports.

## Model commands that work with `--cmd`

The command reads the prompt on stdin and prints the answer. Examples:

- a local model: `ollama run llama3.2`
- a CLI for hosted models, for example `llm -m <model>` (set temperature with its options)
- your own script: `python call_model.py --temperature 0` that reads stdin and calls your provider's API

Run `echo "Say OK" | <cmd>` first to check it. Keep API keys in environment variables, not in the command line.
