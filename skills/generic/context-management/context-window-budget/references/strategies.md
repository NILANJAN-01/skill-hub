# Context window strategies

## Budget layout

```
| system | tools | first task turn | summary of old turns | retrieved docs | recent turns | -> output reserve
  stable --------------------------------------->  changing ----------------------------->
  (cacheable prefix)
```

- Stable parts first, so a prompt cache can reuse them. Anything that changes per call (timestamps, retrieved documents, user-specific data) goes after the last cache point.
- Output reserve: the call's max output tokens must fit in the window together with the input.
- Safety margin: estimates drift; keep 5 to 10%.

## Measuring

- Use the provider's token-counting endpoint or tokenizer for exact numbers; characters / 4 is a rough estimate for English text and code (other languages often use more tokens per character).
- Count before each call; the response's usage numbers tell you what the last call really used.
- Track per part (system, tools, retrieval, history, tool results) so you know what to cut.

## Strategies in detail

### Cap tool output at the source

Best fix, because nothing large enters the context. Give tools `offset`/`limit` or `max_lines` arguments, return the first error plus a path to the full log, return counts and samples instead of whole result sets, and paginate. See `agent-tool-design` for tool output design.

### Truncate old tool results

Keep the head and tail of a large result with a marker in between: `[... 8000 tokens trimmed ...]`. Good for logs and command output where the start (command, first error) and end (summary, exit status) matter.

### Clear old tool results

Replace an old result with a placeholder: `[tool result cleared to save context: 5200 tokens; re-run the tool if needed]`. Keep the tool call so the model knows what was done. Some providers offer this server-side (context editing or tool-result clearing); prefer that when available, it is tested against their API rules.

### Sliding window

Keep the system prompt, the first task turn and the last N turns. Drop whole turns (a user message and everything up to the next user message), never parts of one. Simple and cache-unfriendly at the cut; move the cut in large steps (to the **trim to** level) so it happens rarely.

### Summarise old turns

When dropping turns, ask the model (a cheaper one is fine) for a summary and insert it where the turns were:

```text
Summarise the conversation so far for the assistant that will continue it.
Keep: the user's goal and constraints, decisions and their reasons, facts learned
(names, IDs, numbers, file paths), what was tried and failed, and open items.
Drop: greetings, tool output already acted on, repeated content.
Write at most 300 words as bullet points. Do not invent details.
```

Re-summarise the previous summary plus the newly dropped turns, rather than summarising summaries forever. Test that critical facts survive (`llm-evals`).

### Retrieve history on demand

Store every turn (or a per-turn summary) with an embedding or keyword index; at each call, retrieve the few most relevant past turns instead of keeping them all. Suits assistants with very long or multi-session conversations. See `rag-pipeline`.

### Sub-agents

Run large searches, file reviews or test runs in a separate model call with its own short brief, and put only its short result into the main conversation. See `context-handoff` for the brief template.

## Overflow handling

| Situation | Handling |
|---|---|
| Counted input over the compact threshold | Apply strategies before calling |
| API returns a context-length error anyway | Trim to the **trim to** level and retry once; log it, since estimates were off |
| A single item (file, document, image) is over budget by itself | Chunk it and process in parts, or summarise it in a separate call |
| Output was cut off at max tokens | Raise max output if the window allows, or ask for a shorter format; do not just loop "continue" |

## History manager

A provider-neutral sketch; `count_tokens` and `summarise` are your own functions (provider counter, cheap-model call).

```python
def fit(messages, system, tools, window, max_output, keep_last=8, margin=0.1):
    limit = int(window * (1 - margin)) - max_output
    compact_at, trim_to = int(limit * 0.85), int(limit * 0.6)
    if count_tokens(system, tools, messages) <= compact_at:
        return messages
    starts = [i for i, m in enumerate(messages) if is_real_user_turn(m)]
    protected = next((s for s in reversed(starts) if s <= len(messages) - keep_last), 0)
    msgs = clear_old_tool_results(messages, before=protected)        # placeholders, keep calls
    if count_tokens(system, tools, msgs) <= trim_to:
        return msgs
    first_turn_end = starts[1] if len(starts) > 1 else len(msgs)
    old = msgs[first_turn_end:protected]                              # whole turns only
    summary = summarise(old)
    return msgs[:first_turn_end] + [summary_message(summary)] + msgs[protected:]
```

Make sure `summary_message` keeps the roles valid for your API (for example, merge it into the next user message rather than adding two user messages in a row if the API requires alternation). `scripts/context_budget.py trim` implements the same rules and is a good test oracle.

## Checklist before shipping

- [ ] Window, output reserve and margin are set per model, not hard-coded once.
- [ ] Tool outputs are capped at the source.
- [ ] Trimming keeps tool call and result pairs together and never removes the task.
- [ ] Stable prefix comes first; cache hit rate is monitored.
- [ ] Long-conversation tests pass (`llm-evals`), including facts from early turns.
- [ ] Logs record token counts and trimming actions, not raw prompts.
