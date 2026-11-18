---
name: context-window-budget
description: "Manage the context window of an LLM app or agent loop you are building: split the window into budgets (system, tools, retrieval, history, output), see where a transcript's tokens go, and trim it to fit by truncating or clearing old tool results and dropping whole old turns without breaking tool-call pairs. Covers summaries, caching-friendly order and overflow errors. Use when a chatbot or agent hits context length errors, gets slow or costly as conversations grow, or needs a history strategy."
license: MIT
compatibility: Needs Python 3.8+ (standard library only) for the script. Provider-neutral; reads role/content transcripts with content blocks or tool_calls. Token counts are estimates (characters / 4, images ~1600); use the provider's token counter for exact numbers.
metadata:
  title: "Context window budget: fit LLM conversations into the window"
  category: context-management-tools
---

# Context window budget

Every model call re-sends the whole prompt: system prompt, tool definitions, retrieved documents and the conversation so far. In an agent loop the history (mostly tool output) grows each step until the call fails or quality drops. This skill gives each part a budget and applies a history strategy in code.

## When to use

- An app or agent loop fails with "context length exceeded", "prompt is too long" or similar.
- Cost or latency climbs as conversations get longer; answers degrade late in a conversation.
- Designing the history, retrieval or tool-output policy for a chatbot or agent.

## When NOT to use

- The coding agent you are talking to is running out of context: use `context-handoff`.
- Cutting token waste in a repository for AI tools: use `ai-token-saver`.
- Choosing what to retrieve and how to chunk it: use `rag-pipeline` (this skill only budgets its size).

## Procedure

1. **Plan the budget** for the model's window (read-only):
   ```bash
   python scripts/context_budget.py plan --window 200000 --system 3000 --tools 6000 --output 8000 --retrieval 20000
   ```
   It prints each part's share, a 10% safety margin, and two thresholds: **compact at** (start summarising or trimming) and **trim to** (where to land after trimming, so it does not trigger again next turn).
2. **Measure a real transcript** (export one request's messages as JSON or JSONL):
   ```bash
   python scripts/context_budget.py analyze <transcript.json> --window 200000
   ```
   It reports tokens by role and kind (text, tool_call, tool_result, image, thinking), the largest items, repeated tool results, old tool results, and tips.
3. **Pick a strategy** from the table below (details in [references/strategies.md](references/strategies.md)). Usually combine them in this order: cap tool output at the source, truncate old tool results, clear old tool results, then drop or summarise old turns.
4. **Try it on the transcript** before changing code:
   ```bash
   python scripts/context_budget.py trim <transcript.json> --budget 120000 --keep-last 8 --out trimmed.json
   ```
   The last `--keep-last` messages (snapped back to a turn start) and the first task turn are never changed; tool calls and their results stay together. Exit code 1 means it still does not fit. `--summary "<text>"` puts a summary where turns were removed.
5. **Implement the policy in the app**: count tokens with the provider's counter before each call, apply the same steps when over **compact at**, and log what was trimmed. A reference implementation is in [references/strategies.md](references/strategies.md#history-manager).
6. **Verify** with long test conversations (`llm-evals`): the task, the user's constraints and recent tool results must survive trimming; answers must not get worse.

## Strategies

| Strategy | Use when | Cost |
|---|---|---|
| Cap tool output at the source | Tools return whole files, logs or API dumps | Tool must support ranges or summaries |
| Truncate old tool results (head + tail) | Results are large, only the start and end matter | Middle detail lost |
| Clear old tool results (placeholder) | Agent loops; the model can re-run the tool | Re-fetch if needed again |
| Sliding window of turns | Chat with little long-term state | Old facts forgotten |
| Summarise old turns | Long tasks with decisions to keep | An extra model call; summary can drift |
| Retrieve history on demand | Very long or multi-session conversations | Needs search over past turns |
| Sub-agents with briefs | Big searches or reviews inside a task | Only their short result enters the main context |

## Rules that prevent subtle bugs

- Never separate a tool call from its result, and never leave a result whose call was removed; most APIs reject that.
- Keep the system prompt, tool definitions and the first task message first and unchanged, so prompt caching keeps working; put changing content (retrieval, recent turns) last.
- Trim to well below the limit (the **trim to** value), not just under it, or every turn will trim again and invalidate the cache.
- Reserve the output budget: input + max output must fit in the window.
- Images and documents count heavily; drop or downscale old ones first.

## Safety rules

- `trim` writes only to `--out`, never over the input or an existing file. Transcripts may hold personal data: keep them out of the repository and do not upload them anywhere without the user's agreement.
- Do not log full prompts in production without a data policy; log token counts and what was trimmed.

## Troubleshooting

| Symptom | Fix |
|---|---|
| API error about a tool result without a matching call | The trimming code split a pair: drop whole turns, as `trim` does |
| Model forgets the task after trimming | Keep the first user turn, or restate the task in the summary |
| Cache hit rate drops after adding trimming | Something before the cache point changes each call: move it later |
| `trim` exit code 1 | The protected tail alone is too big: lower `--keep-last` or `--tool-max`, or shorten system and tools |
| Estimates differ from the bill | The script estimates (chars / 4); calibrate with the provider's token counter |

## References

- [references/strategies.md](references/strategies.md): each strategy in detail, summary prompts, caching order, overflow handling and a history-manager implementation
