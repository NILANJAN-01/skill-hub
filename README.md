# skill-hub

A collection of AI Agent Skills (`SKILL.md` playbooks) that AI coding agents such as Claude Code can load and act on, plus the tool that generates them from technical PDFs.

## What's inside

| Path | What it is |
|---|---|
| [`git-skills/skills/`](git-skills/skills/) | 60 Git skills extracted from the *Pro Git* book: rebasing, hooks, advanced merging / merge conflicts, reset, stash, submodules, bisect (debugging), rewriting history, internals and more. See the [catalog](git-skills/skills/README.md). |
| [`git-skills/skillforge.py`](git-skills/skillforge.py) | The generator: turns any technical PDF into a library of focused skills. |

## Using the skills

Copy the skill folders you want into one of these locations:

- `~/.claude/skills/` - available in all your projects
- `<your-project>/.claude/skills/` - only for that project

An agent reads each skill's `description` and loads the full skill only when the task matches, e.g. *"rebase my feature branch onto main"* triggers `git-rebasing`.

Every skill follows the same layout:

```
skills/<name>/
  SKILL.md                    # the playbook
  references/
    source-text.md            # cleaned source text the skill was built from
    procedures.md             # extra procedures (large topics only)
```

`SKILL.md` sections: **When to use**, **When NOT to use**, **Key concepts**, **Safety rules for the agent** (warnings from the source plus destructive commands that need user confirmation), **Procedures** (step -> exact command -> expected output), **Command reference**, **Decision guide**, **Troubleshooting** (error message -> what to do), **Related skills**, **Source** (page numbers).

## Generating skills from a PDF

`skillforge.py` runs fully offline with open-source NLP. It needs no API keys and no LLM.

```bash
cd git-skills
pip install -r requirements.txt     # pymupdf, numpy, scikit-learn, yake

# one skill per section that contains commands
python skillforge.py your-book.pdf

# or only the topics you care about (each topic gathers content from the whole book)
python skillforge.py your-book.pdf --topics "rebase, hooks, merge conflicts, bisect"

# review / edit the plan before writing skills
python skillforge.py your-book.pdf --plan-only
```

How it works:

1. **Parse**: PyMuPDF reads fonts and layout to separate headings, prose, code blocks, inline code, figure captions and note/tip/warning callouts.
2. **Index**: every subsection is indexed with scikit-learn TF-IDF, using light stemming so rebase / rebasing / rebased match.
3. **Plan**: topics are matched to the best sections across the book and saved to `skills/.work/<pdf>/plan.json`, which you can edit before generating.
4. **Author**: each skill is written by extraction. Procedures come from "instruction -> command -> output" sequences, key concepts from TextRank, keyphrases from YAKE, and safety rules and troubleshooting from callouts and error messages.

Every statement in a generated skill is quoted from the source, so it stays faithful to the book, though some extracted bullets can be noisy. Review the skills before you rely on them. Source PDFs are not stored in this repo.

## Credits

The Git skills are derived from [*Pro Git*](https://git-scm.com/book) by Scott Chacon and Ben Straub, licensed under [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/).
