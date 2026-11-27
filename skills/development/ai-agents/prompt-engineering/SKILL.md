---
name: prompt-engineering
description: "Write, fix and improve prompts for an LLM: pick a technique (few-shot, chain-of-thought, decomposition, self-consistency, self-critique), design exemplars, define the answer format, and lint a prompt for known failure modes with a bundled script. Use when the user writes a system prompt or prompt template, or says the model's answers are wrong, inconsistent or badly formatted."
license: "CC-BY-4.0. Original summary of The Prompt Report (Schulhoff et al., 2024, arXiv:2406.06608, CC BY 4.0); scripts MIT. See THIRD_PARTY_NOTICES.md"
metadata:
  title: "Prompt engineering: techniques and prompt lint"
  category: ai-agent-tools
  source: "The Prompt Report: A Systematic Survey of Prompt Engineering Techniques, Schulhoff et al., arXiv:2406.06608v6, 2025"
  pages: "Sections 1-2, 4.2, 5.2, 6"
---

# Prompt engineering

A prompt has parts: a **directive** (the instruction or question), optional **exemplars** (worked examples), **output format** and **style** instructions, a **role**, and **additional information** (the data to work on). Prompt engineering is a loop: run the prompt on a set of real inputs, score the outputs, change one thing, repeat. Small, meaning-preserving edits (spacing, delimiters, exemplar order, option order) can swing accuracy by tens of points, so judge every change on data, never on one example.

## When to use

- Writing or reviewing a system prompt, prompt template or few-shot prompt.
- Answers are wrong, inconsistent between runs, or in the wrong shape; the model agrees with whatever the user says.
- Choosing between zero-shot, few-shot, chain-of-thought, decomposition or ensembling for a task.

## When NOT to use

- Building a labeling or classification prompt and measuring precision/recall: use `llm-classification-prompts` (it builds, runs and scores variants).
- Running eval suites, regressions or LLM-as-judge for an app: use `llm-evals`.
- Prompt injection, jailbreaks or prompt leaking: use `llm-app-security`.
- Choosing what goes into an agent's context window or instruction files: use `context-engineering`.

## Procedure

1. **Lint the prompt** (paths relative to this skill's folder):
   ```bash
   python scripts/prompt_lint.py prompt.txt          # also .md, or .json chat messages; - reads stdin
   ```
   Fix every MEDIUM finding: unbalanced or grouped exemplar labels, mixed exemplar formats, no answer space for a labeling task, reasoning without a final-answer marker, the user's opinion in the prompt, inserted input without delimiters.
2. **Get 20+ real inputs with expected outputs** before tuning. Without a dev set you cannot tell a better prompt from a lucky one.
3. **Start simple**: a clear directive, the allowed answers, delimited input. Add one technique at a time from the decision guide below and keep it only if the dev-set score improves. Re-run a variant 2-3 times: scores move a few points between runs even at temperature 0.
4. **Engineer the answer**: restrict the answer space ("Answer with one word: Yes or No"), and parse with a fixed rule. After chain-of-thought, take the **last** match of the answer marker, not the first.
5. **Read the failures.** Ask the model to explain a wrong answer (the explanation is a plausible story, not its real process) and turn the pattern into an instruction or a contrastive exemplar. Check with the person who owns the task that the fix matches the real goal: optimizing a dev-set score can drift away from it.
6. **Re-check after model changes.** The same prompt can behave differently on a new model version (prompt drift); keep the dev set and re-run it.

## Decision guide

| Situation | Try first | Then |
|---|---|---|
| Simple task, model knows it | Zero-shot with a precise directive and answer format | Role or style instruction for tone |
| Output shape or labels inconsistent | 3-10 exemplars: balanced labels, shuffled, same format as the real input, similar to it | Pick exemplars per input by similarity (kNN) |
| Maths, logic, multi-step reasoning | Chain-of-thought ("think step by step", then "Final answer:") | Few-shot CoT; Plan-and-Solve wording |
| Problem has separable parts | Least-to-Most: list sub-problems, then solve in order | Code as reasoning (Program-of-Thoughts) for calculation |
| Answers vary run to run | Self-consistency: 3-5 samples at temperature ~0.5, majority vote | Vary exemplar order or wording across samples |
| Factual errors in long answers | Chain-of-Verification: draft, list check questions, answer them, revise | Retrieval (see `rag-pipeline`) |
| Quality needs polish | Self-Refine: critique, then rewrite, 1-3 rounds | Separate critic prompt |
| Ambiguous user request | Ask clarifying questions before answering | Rephrase-and-respond |

Details, more techniques and the evidence behind each: [references/techniques.md](references/techniques.md).

## Safety rules for the agent

- Don't put personal or confidential data in prompts sent to a third-party model unless the user agreed; replace names and emails with placeholders.
- Don't claim a technique "improves accuracy" for the user's task without measuring it there; published gains often do not transfer between models and datasets.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Output wraps the label in a sentence ("It's positive because...") | State the allowed answers and form; parse with a rule; add an extraction step only for unparsed outputs |
| Chain-of-thought made accuracy worse | It happens (the paper's MMLU run saw it); keep it only where the dev set shows a gain |
| Model always picks the same label | Balance and shuffle exemplars; check the label of the last exemplars |
| Model agrees with a wrong claim | Remove opinions and "are you sure?" pushback from the prompt; ask neutrally |
| Model refuses or gives advice instead of a label (sensitive topics) | Make the labeling task explicit ("Is this X? Yes or No"); a different model may be needed |
| Long structured output loses quality | Try with and without the format constraint; validate format separately |
