---
name: skillforge
description: "Turn a technical PDF (book, manual, handbook, spec) into a library of Agent Skills with the bundled offline generator (no LLM or API key). Use when the user wants to create skills from a PDF, convert a book or documentation into SKILL.md playbooks, or regenerate skills that were built from a document."
license: Complete terms in the repository README
metadata:
  title: "Skillforge: PDF to skills"
  category: hub-tools
---

# Skillforge: PDF → Agent Skills

`scripts/skillforge.py` reads a technical PDF and writes one focused skill per actionable topic. Each skill has two parts, so that using it saves tokens: a short `SKILL.md` (about 500 tokens: safety rules, the commands, the fixes, related skills), read every time the skill is used, and `references/playbook.md` with the full playbook (When to use, Key concepts, Safety rules, Procedures, Command reference, Decision guide, Troubleshooting, Source), read only when a step needs it. It runs fully offline. Every statement it writes is **extracted** from the source, never invented.

The 61 `git-*` skills in this hub were produced with it from *Pro Git*.

## When to use

- The user has a PDF (book, manual, runbook, vendor docs) and wants skills from it.
- The user wants skills for only certain topics of a document ("rebase, hooks, bisect").
- The user wants to rebuild one skill after editing the plan.

## When NOT to use

- The source is not a PDF (web pages, Markdown docs). Write the skill by hand from `template/SKILL.md.tmpl` (or run `python tools/hub.py new-skill` in skill-hub) instead.
- The user wants a single hand-crafted skill with judgment or workflow. Use the `contribute-skill` skill instead.
- The document is mostly prose without commands or procedures. Extraction gives thin skills; tell the user.

## Setup

Nothing to install: the scripts use only the Python standard library (Python 3.8+). The PDF reader (`pdf_lite.py`) and the text statistics (`nlp_lite.py`) are bundled. If PyMuPDF happens to be installed, `--engine pymupdf` uses it instead of the bundled reader. The output is the same apart from small spacing differences.

All paths below are relative to this skill's folder. Use the absolute path of `scripts/skillforge.py` if you run it from somewhere else.

## Procedure

1. **Confirm the inputs.** Ask for or confirm the PDF path, an optional topic list, and the output folder. Do not commit or redistribute the source PDF, which is usually copyrighted. Note the document's license in the generated skills.
2. **Plan first** for large documents:
   ```bash
   python scripts/skillforge.py book.pdf --plan-only --out generated-skills
   ```
   This prints the planned skills with page ranges and writes `generated-skills/.work/<pdf>/plan.json`. Show the list to the user. They can rename skills or drop units in `plan.json`.
3. **Generate**:
   ```bash
   # one skill per section that contains enough commands
   python scripts/skillforge.py book.pdf --out generated-skills
   # or only chosen topics, each gathering content from the whole document
   python scripts/skillforge.py book.pdf --out generated-skills --topics "rebase, hooks, merge conflicts"
   # rebuild specific skills after editing plan.json
   python scripts/skillforge.py book.pdf --out generated-skills --only git-rebasing,git-hooks
   ```
   Other options: `--prefix` (skill-name prefix, guessed by default), `--max-skills` (default 60), `--min-commands` (default 3), `--replan`.
4. **Review** the output. The script prints any problems per skill (for example "no procedures"). Open a few skills (`SKILL.md` and `references/playbook.md`) and check:
   - the `description` is rewritten by hand. The generated one is only a draft, and the description is the only text an agent reads when it decides whether to load the skill. Start with the task in the words a user would type ("Undo mistakes: amend the last commit, unstage a file ..."), then "Use when ..." with real commands and error messages. Keep it under about 300 characters, because agents shorten or drop descriptions when many skills are installed;
   - the procedures (in `references/playbook.md`) are in order and the commands are complete;
   - noisy or irrelevant bullets are removed (extraction is faithful but can be noisy).
5. **Publish into the hub** (when working in the skill-hub repo): follow the `contribute-skill` skill. Copy the reviewed folders into `skills/`, add `license` and `metadata` (title, category, source, pages) to each frontmatter, register them in `.claude-plugin/marketplace.json`, then run `python tools/build_catalog.py` and `python tools/validate_skills.py`.

## How it works (for explaining results)

1. **Parse.** `pdf_lite.py` reads each character with its font, size and position (it handles compressed and damaged files, object streams, embedded and CID fonts, ToUnicode maps and empty-password encryption). Font size, monospace runs and layout then tell apart headings, prose, code blocks, inline code, captions and note/warning callouts. Text hidden by a clipping path is skipped.
2. **Index.** Each subsection is indexed with TF-IDF (`nlp_lite.py`, same weights as scikit-learn's `TfidfVectorizer`) and light stemming, so rebase, rebasing and rebased match.
3. **Plan.** Topics are matched to the best sections across the whole document. The plan is editable JSON that later runs reuse.
4. **Author.** Each output section comes from a different extraction method:
   - Procedures: "instruction → command → output" sequences.
   - Key concepts: TextRank (PageRank over sentence similarity).
   - Keyphrases: YAKE.
   - Safety rules: callouts plus destructive commands.
   - Troubleshooting: error lines in output, each paired with the sentence that resolves it.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot read book.pdf: The PDF is password-protected.` | The file needs a real password. Remove it with a PDF tool you trust, then rerun |
| Text looks garbled (`�`, missing letters) | The PDF's fonts have no Unicode map (common with old TeX bitmap fonts). Try `--engine pymupdf` if PyMuPDF is installed; otherwise OCR the file |
| Few or no skills planned | Lower `--min-commands`, or pass `--topics` explicitly |
| Skill reports "no procedures" | The matched sections have no commands. Drop the skill or merge topics |
| Headings detected wrongly (scanned PDF) | The PDF needs a text layer. Run OCR first (e.g. `ocrmypdf`) |
| Plan ignores your new options | Options changed but the plan is cached. Add `--replan` |
