# Third-party notices

## Pro Git (2nd edition)

The skills under `skills/development/git-*/` (every `git-*` skill) (including `references/` files) are adapted, by automated extraction, from:

> *Pro Git*, 2nd edition, by Scott Chacon and Ben Straub. Published by Apress. https://git-scm.com/book

*Pro Git* is licensed under the [Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License (CC BY-NC-SA 3.0)](https://creativecommons.org/licenses/by-nc-sa/3.0/).

These derived skills are distributed under the same license, CC BY-NC-SA 3.0:

- **Attribution**: credit Scott Chacon and Ben Straub and link to the license.
- **NonCommercial**: you may not use the material for commercial purposes.
- **ShareAlike**: if you remix or build on the material, you must distribute your contributions under the same license.

Changes made: the text was split into topic-focused skills, reorganized into fixed sections (procedures, safety rules, troubleshooting, etc.), and lightly cleaned. Page numbers of the original are cited in each skill's `metadata.pages` and in its **Source** section.

## Android Developers documentation (UI Automator)

The UI Automator skills under `skills/testing/uiautomator/` (`uiautomator-test-authoring`, `uiautomator-migration`, `uiautomator-run-debug`), including their `references/` files, are written from the Android Developers documentation and the AndroidX UI Automator API reference and source (listed in `uiautomator-test-authoring/references/sources.md`), by Google / the Android Open Source Project.

Documentation text on developer.android.com is licensed under the [Creative Commons Attribution 4.0 License (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/); code samples and the AndroidX source are licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

Changes made: the material was paraphrased and reorganised into task-focused skills, cross-checked against the 2.4.1 API reference and library source (with differences noted in `sources.md`), and extended with original scripts, examples and troubleshooting.

## JUnit User Guide (JUnit skills)

The JUnit skills under `skills/testing/junit/` (`junit-test-authoring`, `junit-migration`, `junit-run-reports`), including their `references/` files, are written from the JUnit 6 User Guide and release notes (https://docs.junit.org/, listed in `junit-test-authoring/references/sources.md`) by the JUnit team.

The User Guide content is made available under the [Eclipse Public License v2.0 (EPL-2.0)](https://www.eclipse.org/legal/epl-2.0/), the same licence as JUnit. The Open Test Reporting schemas referenced by `junit-run-reports` are from the ota4j-team/open-test-reporting project.

Changes made: the material was paraphrased and reorganised into task-focused skills, Java examples were checked by compiling them against the JUnit 6.1.3 artifacts, and original scripts, examples and troubleshooting were added.

## A Philosophy of Software Design (software design skills)

The skills under `skills/development/software-design/` (`software-design-guardrails`, `deep-modules`, `error-handling-design`, `obvious-code`, `design-it-twice`) are based on the ideas in:

> *A Philosophy of Software Design* by John Ousterhout. Yaknyam Press, 2018. ISBN 978-1-7321022-0-0.

The book is copyrighted (all rights reserved) and is **not** included in this repository. These skills do not reproduce its text: the principles and red flags are summarised in original words, the examples are original, and each skill cites the chapters it draws on so readers can consult the book for the full reasoning. The scripts (`design_check.py`, `install_guardrails.py`, `design_note.py`) are original work. All of this material is distributed under the repository's MIT license.

Changes made: the book's ideas were reorganised into five task-focused skills with procedures, checklists and decision guides, and extended with original tooling that checks code and design notes for the red flags the book describes.

## The Prompt Report (prompt engineering skills)

The skills `prompt-engineering`, `llm-classification-prompts` and `llm-app-security` under `skills/development/ai-agents/`, including their `references/` files, are based on:

> Sander Schulhoff, Michael Ilie, Nishant Balepur, et al. *The Prompt Report: A Systematic Survey of Prompt Engineering Techniques*. arXiv:2406.06608v6, 2025. https://arxiv.org/abs/2406.06608

The paper is licensed under the [Creative Commons Attribution 4.0 International License (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). The paper itself is not included in this repository.

Changes made: the survey's taxonomy, findings and case study were summarised in original words and reorganised into three task-focused skills with procedures, decision guides and troubleshooting; short technique phrases (thought inducers, attack examples) are quoted. The scripts (`prompt_lint.py`, `prompt_bench.py`, `llm_sec.py`) are original work under the repository's MIT license; `prompt_bench.py` implements the paper's AutoDiCoT procedure.
