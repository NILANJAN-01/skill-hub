# RAG design notes

## Chunking strategies

| Strategy | Use when |
|---|---|
| Fixed size with overlap | Plain unstructured text; baseline |
| Structure-aware (headings, paragraphs) | Markdown, HTML, docs sites: usually best default |
| Code-aware (functions, classes) | Source code; keep imports/signatures as context |
| Row or record based | Tables, CSV, tickets: one record per chunk, with column names |
| Parent-child ("small to big") | Retrieve small chunks for precision, pass their larger parent section to the model |
| Contextual chunks | Prepend a short generated summary of the document/section to each chunk before embedding; improves recall on ambiguous chunks |

Rules of thumb: one topic per chunk; include the heading path; keep code blocks and tables whole; test 2 or 3 sizes with the retrieval test set rather than guessing.

## Hybrid search with reciprocal rank fusion

For each candidate document d, over each ranked list r (BM25, vector, ...):

```
score(d) = sum over lists of 1 / (k + rank_r(d))      with k = 60 (common default)
```
Ranks start at 1. Documents missing from a list contribute nothing for it. Sort by score and keep the top N for reranking.

## Reranking

A cross-encoder or hosted reranker reads the query and each candidate together and scores relevance. It is slower than vector search, so apply it to the top 20 to 50 candidates only. Typically the largest single gain after hybrid search.

## Prompt template

```
Answer the question using only the sources below. Cite the source ids you used in square brackets, e.g. [docs/security.md#2].
If the sources do not contain the answer, say you don't know and suggest where to look.

<sources>
<source id="docs/security.md#2">
...chunk text...
</source>
...
</sources>

Question: {question}
```

## Metrics

- **Hit rate@k**: share of queries with at least one relevant item in the top k.
- **Recall@k**: per query, relevant items found in the top k divided by all relevant items; averaged.
- **MRR**: mean of 1 / rank of the first relevant item (0 if none retrieved).
- **Answer-level** (in `llm-evals`): faithfulness (every claim supported by a cited source), correctness, citation accuracy, refusal on unanswerable questions.

## Advanced patterns

- **Query rewriting**: turn a chatty follow-up into a standalone query using the conversation; or generate several query variants and fuse results.
- **Agentic retrieval**: expose search as a tool so the agent can search, read, and search again; give the tool filters (source, date) and return ids plus snippets.
- **Metadata filters and routing**: route by product/version before searching; enforce permissions as filters.
- **Freshness**: incremental re-indexing keyed on document hash; delete chunks of removed documents.
- **Long-context alternative**: if the relevant corpus fits in the context window, compare RAG against simply including it (with prompt caching) on the same eval set.

## Formats used by rag_tool.py

`chunk` writes one JSON object per line:
```json
{"id": "docs/security.md#2", "source": "docs/security.md", "headings": ["Security", "API keys"], "text": "...", "chars": 1084, "approx_tokens": 271}
```
`score` reads `queries.jsonl` (`id`, `query`, `relevant` list) and `results.jsonl` (`id`, `retrieved` list in rank order).
