---
name: professional-writing
description: "Write, tailor and review professional documents: blog posts, CVs/resumes (tailor to a job post, review), cover letters, technical docs and READMEs, with a checker script and templates. Use when the user wants to write a blog post or article, prepare or improve a CV, match a CV to a job ad, or draft documentation."
license: Complete terms in the repository README
compatibility: Scripts need Python 3.8+ (standard library only). They read .md, .txt and .docx; export a PDF to text or .docx first.
metadata:
  title: "Professional writing: blog, CV, docs"
  category: writing-tools
---

# Professional writing

Helps produce a blog post, CV, cover letter or technical document that is accurate, specific and easy to read. Two scripts do the mechanical work: `scripts/new_doc.py` starts a document from a template, and `scripts/doc_check.py` measures a draft and lists concrete problems. The writing itself, and the judgement, stay with you and the user.

## When to use

- Write a blog post or article (for example a post comparing test tools for Android).
- Prepare a CV from the user's facts, or adapt it to a particular job post.
- Review a CV and say what to fix.
- Draft a cover letter, a technical document, a how-to, a runbook or a README.
- Check a draft's length, readability, structure and cliches.

## When NOT to use

- Writing code, or documenting a codebase from source: use `repo-learnings`.
- Legal, medical or financial documents that need a professional's review.

## Safety rules for the agent

- **Never invent facts.** Don't make up jobs, dates, metrics, employers, degrees, certifications, tool versions, benchmark numbers or quotes. If a fact is missing, ask, or leave a visible `<placeholder>`.
- Don't add a skill or keyword to a CV unless the user confirms it is true. Tailoring means choosing and rewording real experience, not adding fake experience.
- A CV contains personal data. Work on local files only, don't paste it into web forms or external services, and don't put names, phone numbers or addresses into commands or search queries.
- Don't overwrite the user's file. Write edits to a new file (for example `cv-acme.md`) and keep the original.
- For blog posts about tools, check claims against official documentation before stating them, and say which versions and dates were tested. Don't present untested behaviour as fact.

## Procedure

### A. Blog post or article

1. Ask (or infer from the request) the audience, the single outcome the reader gets, the tools or topics covered, the length, and which facts the user can verify (what they actually ran).
2. Create a draft file: `python scripts/new_doc.py blog post.md --title "Working title"`.
3. Build the outline first and show it to the user: problem, short answer, how it was tested, one section per option, pitfalls, choice guide, takeaways. See [references/blog.md](references/blog.md) for the structure, a worked outline for an Android test-tools comparison, and an accuracy checklist.
4. Draft section by section from the user's real experience. Mark every claim that still needs checking.
5. Run the checker, then fix the findings that matter:
   ```bash
   python scripts/doc_check.py post.md --type blog
   ```
6. Revise: concrete examples, active verbs, short sentences, a title that names the reader and the result. Add a "Tested with ... as of <date>" line and source links.

### B. Prepare a CV for a job post

1. Get the user's current CV (any text form) and the full job post saved as a text file.
2. Extract the job's top requirements (must-haves first), then map each to a real item in the CV. List requirements with no match and ask the user whether they have that experience.
3. Create the tailored file from the user's own content (or start from the template: `python scripts/new_doc.py cv cv-acme.md --title "Full Name"`).
4. Rewrite the summary and the order of bullets so the best matches come first. Reword with the job post's vocabulary where it is true. Keep each bullet as: action verb, what, result with a number.
5. Check keyword coverage and structure:
   ```bash
   python scripts/doc_check.py cv-acme.md --type cv --job job.txt
   ```
6. Optionally draft a cover letter (`new_doc.py cover-letter`), using one concrete example per top requirement.
7. Tell the user what was changed and what is still missing. See [references/cv.md](references/cv.md).

### C. Review a CV

1. Run `python scripts/doc_check.py cv.md --type cv` (add `--job job.txt` if there is a target job).
2. Combine the script output with the manual rubric in [references/cv.md](references/cv.md): first-screen impact, relevance, proof of results, clarity, consistency, length, ATS-friendliness.
3. Report in this order: the 3 most important fixes, then smaller issues, then what is already strong. Quote the exact line and show a better rewrite, and ask for the real numbers when a bullet has none.

### D. Technical document, README or how-to

1. `python scripts/new_doc.py doc guide.md --title "..."` (or `readme`).
2. Write for one named reader. Put the purpose first, then numbered steps in the imperative, each with an exact command and the expected result. Add a troubleshooting table.
3. Run `python scripts/doc_check.py guide.md --type doc` and fix long sentences and filler.

## Script reference

| Command | What it does |
|---|---|
| `new_doc.py --list` | Lists templates: blog, cv, doc, readme, cover-letter |
| `new_doc.py KIND OUT [--title T] [--force]` | Creates OUT from a template; refuses to overwrite without `--force` |
| `doc_check.py FILE [--type blog\|cv\|doc] [--job JOB.txt] [--json]` | Word count, reading time, sentence length, readability, passive voice, filler words; blog structure checks; CV section, bullet, number and date checks; job keyword coverage |

The checks are heuristics. A clean report does not mean the document is good, and a warning is a place to look, not an error. Read the final text aloud once.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `PDF is not read directly` | Export the PDF to .docx or text, or paste its text into a .txt file |
| Wrong document type guessed | Pass `--type blog`, `--type cv` or `--type doc` |
| `already exists` from `new_doc.py` | Pick another file name, or pass `--force` if the user agrees |
| Job keyword list contains noise | Edit the job text file to keep only the requirements section and re-run |
| Everything is flagged as passive | The check is crude; ignore it for text with many technical terms ending in -ed |

## References

- [references/blog.md](references/blog.md): blog structure, Android test-tools example outline, accuracy checklist
- [references/cv.md](references/cv.md): CV rules, bullet formula, review rubric, tailoring steps
