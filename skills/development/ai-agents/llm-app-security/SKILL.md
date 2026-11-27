---
name: llm-app-security
description: "Secure an app that calls an LLM against prompt injection, jailbreaks, prompt leaking and hallucinated packages: a bundled script finds model output reaching eval, shell, SQL or HTML, user input in system prompts, secrets in prompts, unknown imports in generated code, and runs injection probes against your prompt. Use when building or reviewing a chatbot, agent or LLM feature, or checking AI-generated code before installing its dependencies."
license: "CC-BY-4.0. Threat model from The Prompt Report (Schulhoff et al., 2024, arXiv:2406.06608, CC BY 4.0), section 5.1; scripts MIT. See THIRD_PARTY_NOTICES.md"
metadata:
  title: "LLM app security: prompt injection and hallucinated packages"
  category: ai-agent-tools
  source: "The Prompt Report: A Systematic Survey of Prompt Engineering Techniques, Schulhoff et al., arXiv:2406.06608v6, 2025"
  pages: "Section 5.1"
---

# LLM app security

A model cannot reliably tell the developer's instructions from instructions hidden in user input or documents. That is **prompt injection**, and no prompt wording fully prevents it. The defences that work limit the **damage**: whatever the model outputs, it must not be able to run code, reach data or take actions the user could not take anyway. `scripts/llm_sec.py` (Python 3.8+, standard library only) checks code for the common mistakes and tests a prompt against injection.

## When to use

- Building or reviewing a chatbot, RAG app, agent or any feature that sends user or web text to a model.
- Model output is executed, rendered as HTML or Markdown, used in SQL or shell commands, or used to call tools.
- AI-generated code imports packages you don't recognise (hallucinated packages can be registered by attackers).
- Someone asks "can users jailbreak or extract our system prompt?"

## When NOT to use

- Leaked API keys or dependency pinning across a repository: use `secrets-dependency-audit`.
- Wrong or inconsistent answers (quality, not security): use `prompt-engineering`.
- Designing tool schemas for an agent: use `agent-tool-design` (then check its tools' permissions here).

## Safety rules for the agent

- Run `probe` only against the user's own app and models, never against third-party services without permission.
- Never install a package that `imports` flags until its registry page, owner and repository are checked with the user.
- Don't claim an app is "safe from prompt injection". Report what was tested and what limits the damage.
- Keep found secrets masked in reports, and tell the user to rotate them.

## Procedure

Paths are relative to this skill's folder.

1. **Map the data flow.** Where untrusted text enters (user messages, uploaded files, web pages, emails, tool results), what the model can do (tools, API calls), and where its output goes (UI, database, shell, other prompts).
2. **Scan the code and prompts**:
   ```bash
   python scripts/llm_sec.py scan src/ prompts/
   ```
   HIGH means model output reaches `eval`/`exec`, a shell, SQL text or deserialisation, or a secret sits in a prompt. MEDIUM means a system prompt is built from user text, or model HTML/Markdown is rendered raw. Fix each with the printed advice.
3. **Check generated code before installing anything**:
   ```bash
   python scripts/llm_sec.py imports generated/ --online
   ```
   Offline it lists imports that are not stdlib, installed, declared or local. `--online` asks PyPI/npm: *missing* means hallucinated; *first published in the last 90 days* means it may be squatted.
4. **Probe the prompt** with the app's real template (`{INPUT}` where user text goes, optional `{CANARY}` in the instructions) and a command that calls the same model:
   ```bash
   python scripts/llm_sec.py probe --template app_prompt.txt --cmd "ollama run llama3.2" --samples 3
   ```
   It sends 12 attacks (override, fake new task, role-play, delimiter escape, hidden instructions in a document, payload splitting, base64, other language, four prompt-leak styles). A hijack succeeds if the output contains a random marker; a leak succeeds if the canary comes back. `--export cases.jsonl` writes the attacks for an eval suite (`llm-evals`).
5. **Harden**, in order of strength:
   - Give the model's output no more power than the user has: least-privilege tools and API keys, read-only DB users, an allowlist of actions, and human confirmation for anything that sends, pays, deletes or publishes.
   - Treat output as untrusted data: parse JSON against a schema, map choices to an allowlist, escape HTML, strip Markdown images and links (they can carry data out).
   - Keep secrets and access rules out of prompts: assume the whole prompt can be extracted.
   - Keep the system prompt fixed and put untrusted text in the user message, inside delimiters, labelled as data.
   - Add an input/output detector or guardrail for known attacks (fine-tuned detectors beat prompt-only defences), and rate-limit.
   - Re-run `probe` after each change and after model upgrades.

Threats, real incidents and more defences: [references/threats.md](references/threats.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `scan` flags a parameterised query | It skips `execute("... ?", params)`; a query built with f-strings or `+` is flagged on purpose |
| `scan` misses a flow | It tracks names within one file; review flows across files and through tools by hand |
| `imports` flags your own module | Pass `--root` at the project root so local packages and requirements are found |
| `probe` blocks everything, but users still break it | Attacks vary; add the user's real attack text to an eval suite and limit damage (step 5) |
| `probe` exits 2 | The model command failed; test it: `echo hi \| <cmd>` |
