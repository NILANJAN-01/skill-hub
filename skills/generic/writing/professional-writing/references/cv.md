# CV guide: prepare, tailor, review

## Basics

- Length: 1 page for under about 8 years of experience, 2 pages after that. Cut old or minor roles first.
- Order: contact, summary, skills, experience (newest first), projects, education, certifications. Put education first only for new graduates.
- Plain structure: standard headings, one column, no text in images or tables, a normal font. Many applicant tracking systems read plain structures best.
- Contact: email, phone, city, LinkedIn/GitHub. Leave out date of birth, marital status and photo unless the target country expects them.
- File name: `Firstname-Lastname-CV.pdf` (or `-Company`). Send a PDF unless asked for another format.

## Bullet formula

`Action verb + what you did + how (tool or method) + result with a number`

- Weak: "Responsible for test automation."
- Better: "Built an Appium + Kotlin regression suite of 240 tests that cut release verification from 2 days to 3 hours."
- No number available? Use scale (devices, users, services, team size), frequency, or before/after in plain words. Ask the user; never invent one.
- Keep bullets to one or two lines, 3-6 per role, strongest first. Past tense for old roles, present for the current one.

## Tailoring to a job post

1. Read the post and mark must-have requirements vs nice-to-have.
2. For each must-have, find the user's real evidence. Record: requirement, matching CV line, gap.
3. Rewrite the summary to mirror the role title and the top 2-3 requirements (only if true).
4. Reorder skills and bullets so matches come first; drop or shorten what is unrelated.
5. Use the post's wording for the same thing (for example "CI/CD pipelines" if the post says that), only when it is accurate.
6. List gaps honestly to the user, with options: add a relevant project, a short course, or address it in the cover letter. Never add a skill the user does not have.
7. Run `doc_check.py --type cv --job job.txt` and review missing keywords one by one: add only the true ones.

## Review rubric (score each 1-5, quote the evidence)

| Area | Questions |
|---|---|
| First screen | Does the top third say who they are, the target role and the strongest proof? |
| Relevance | Does most of the content support the target role? Is anything distracting? |
| Proof | Do bullets show results and numbers, not duties? |
| Clarity | Short sentences, no jargon the reader may not share, no cliches ("team player", "results-driven")? |
| Consistency | Same date format, tense, punctuation, capitalization, and bullet style throughout? |
| Gaps and dates | Are employment gaps or short stays explained or at least not confusing? |
| Length and layout | Right length, readable, nothing cramped, no spelling errors? |
| Integrity | Is everything true and checkable? Titles, dates and tools match what they could verify? |

## Review report format

1. **Top 3 fixes** (highest impact), each with the original line and a rewritten one.
2. **Other issues**, grouped by the rubric areas above.
3. **Strengths** to keep.
4. **Questions** for the user: missing numbers, unclear dates, projects not listed.

## Cover letter (short)

3-4 short paragraphs: the role and why this company, one proof for the top requirement, one more proof or insight into their problem, a clear close. Under 250 words. No repeating the CV line by line.
