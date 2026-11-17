---
name: rag-pipeline
description: "Build and debug a RAG (retrieval-augmented generation) pipeline: chunking, embeddings, hybrid search, reranking, cited answers, with a script that chunks docs and scores retrieval (recall@k, MRR). Use when the user wants to chat with documents, pick a chunk size or vector store, or says retrieval finds the wrong passages."
license: MIT
compatibility: Needs Python 3.8+ (standard library only) for the script. Embedding models and vector stores are whatever the project uses.
metadata:
  title: "RAG pipeline: chunk, retrieve, ground and evaluate"
  category: ai-agent-tools
---

# RAG pipeline

Retrieval-augmented generation answers questions from your own documents: **index** (load → clean → chunk → embed → store) once, then per question **retrieve** (search → rerank → select) and **generate** (prompt with the passages, cite them). Most quality problems are retrieval problems, so measure retrieval separately from answers.

## When to use

- Build a "chat with our docs/code/tickets" feature or a knowledge-base agent tool.
- Choose chunk size, embedding model, vector store, hybrid search or reranking.
- Answers are wrong, vague or uncited and you need to find out whether retrieval or generation is at fault.

## When NOT to use

- The whole corpus fits comfortably in the model's context and changes rarely: put it in the prompt (with caching) instead of building retrieval.
- Exact lookups by ID or structured filters: use a database query or a tool (see `agent-tool-design`).
- Scoring final answer quality: use `llm-evals` after retrieval is good.

## Procedure

1. **Know the questions.** Collect 30+ real questions and, for each, the document (or section) that answers it. This becomes the retrieval test set (`queries.jsonl`):
   ```json
   {"id": "q1", "query": "How do I rotate the API key?", "relevant": ["docs/security.md"]}
   ```
2. **Load and clean.** Extract text with structure (headings, lists, tables, code blocks); drop navigation, boilerplate and duplicates; keep metadata (source path/URL, title, date, access level).
3. **Chunk** by structure first, size second. Start at ~800 to 1500 characters (~200 to 400 tokens) with ~10 to 15% overlap, never splitting code blocks or tables mid-way, and prefix each chunk with its heading path for context:
   ```bash
   python scripts/rag_tool.py chunk docs/ --size 1200 --overlap 150 --out chunks.jsonl
   ```
   It splits Markdown/text by headings, packs paragraphs up to `--size`, adds overlap, keeps fenced code blocks whole when they fit, and prints chunk statistics (count, average/min/max size, tiny chunks). Chunk ids are `<path>#<n>`. Feed `chunks.jsonl` to the project's embedding and indexing code.
4. **Embed and index.** Use one embedding model for documents and queries (some need different query/document prefixes; check its card). Store vectors with the chunk text and metadata. Any vector store works; at small scale (under ~1M chunks) a library or Postgres with pgvector is enough.
5. **Retrieve with hybrid search.** Combine keyword search (BM25; catches names, codes, error strings) with vector search (catches paraphrases), merge with reciprocal rank fusion, retrieve ~20 to 50 candidates, then rerank with a cross-encoder or reranker to the top 3 to 8. Apply metadata filters (product, version, permissions) **before** ranking.
6. **Score retrieval** by running the test queries through your retriever and saving `results.jsonl` (`{"id": "q1", "retrieved": ["docs/security.md#2", "docs/faq.md#7", ...]}` in rank order):
   ```bash
   python scripts/rag_tool.py score queries.jsonl results.jsonl --k 1,3,5,10 --match source
   ```
   It reports recall@k, hit rate@k and MRR, and lists the queries whose relevant documents were not retrieved. `--match source` compares only the part before `#`, so labels can be whole documents. Aim for hit rate@5 of 0.9+ before tuning prompts.
7. **Assemble the prompt.** Put retrieved passages in clearly delimited blocks with their source ids, instruct the model to answer only from them, cite the ids it used, and say "I don't know" when they do not contain the answer. Order passages by relevance; trim to a token budget.
8. **Evaluate answers** with `llm-evals` (faithfulness to passages, correctness, citation present, refusal when unanswerable), and re-run step 6 after every change to chunking, embeddings or search.

## Safety rules

- Enforce document permissions at retrieval time; never rely on the prompt to hide documents a user may not see.
- Retrieved text is untrusted: it can contain prompt-injection instructions. Keep it in delimited data blocks and do not let it trigger tools by itself.
- Do not index secrets or personal data without the owner's approval.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Right doc never retrieved (low recall) | Chunks too large or mixed topics: smaller, heading-based chunks; add BM25 for exact terms; check the query/document prefixes of the embedding model |
| Right doc retrieved but ranked low (low MRR) | Add a reranker; add heading/title text to each chunk |
| Good retrieval, wrong answer | Too many or noisy passages: fewer, reranked passages; stricter "answer only from sources" instruction |
| Answers cite nothing | Ask for citations by source id and check them in `llm-evals` |
| Names, codes or error messages not found | Vector search alone misses exact strings: use hybrid search |
| Outdated answers | Re-index on document change; store and filter by date or version |

## References

- [references/rag-design.md](references/rag-design.md): chunking strategies, hybrid search and RRF, reranking, prompt template, metrics and advanced patterns.
