# Blog post guide

## Choose the post type

| Type | Promise to the reader | Shape |
|---|---|---|
| Comparison | "Which one should I pick?" | Short answer table, criteria, one section per option, verdict by use case |
| How-to | "Do X in N steps" | Prerequisites, numbered steps with commands, expected output, pitfalls |
| Lessons learned | "What went wrong for me" | Context, what happened, cause, fix, what to do differently |
| Deep dive | "How X really works" | Question, mechanism, evidence, limits |

## Title and opening

- Name the reader and the result: "Android UI test tools compared: Espresso, UI Automator and Appium for a small team".
- First 3-4 sentences: the situation, the cost of getting it wrong, what the reader will have by the end.
- Put the conclusion or table early. Do not make readers scroll for it.

## Body rules

- One idea per paragraph; paragraphs under about 120 words.
- Headings should tell the story when read alone.
- Every tool section answers: what it is, when to pick it, when not to, a minimal working example, one real drawback.
- Prefer a measured or observed fact to an adjective. "Cold start of the suite dropped from 9 to 4 minutes on 3 emulators" beats "much faster".
- Show failures. Real error messages and their fixes are what readers search for.

## Worked outline: "Test tools for Android"

1. **Hook:** flaky UI tests cost the team N hours a week (use the user's real number, or no number).
2. **Short answer:** a table of the tools and the situation each fits.
3. **How I evaluated:** app type, devices/emulators, language (Kotlin/Java), CI, criteria such as speed, flakiness, setup effort, debugging, cross-platform, community.
4. **Sections, one per tool** the user actually used. Candidates: Espresso (in-process UI tests), UI Automator (cross-app, system UI), Compose test APIs, Appium (cross-platform, WebDriver), Robolectric (JVM unit tests with Android APIs), Maestro (YAML flows), Detox (React Native), Firebase Test Lab / device farms, JUnit + MockK/Mockito for unit tests, Allure for reports. Only include what the user has evidence for, or label it "not tested, from the docs".
5. **Pitfalls:** synchronization and idling, animations on devices, permissions dialogs, emulator vs real device differences, test data and state, CI timeouts.
6. **Which one when:** a decision list by team size, app type and goals.
7. **Takeaways and next steps:** links to the sample repo and official docs.
8. **Sources and "tested with" line:** Android Gradle Plugin, library versions, API levels, date.

## Accuracy checklist (run before publishing)

- [ ] Every command and code block was run, or is marked as untested.
- [ ] Versions, API levels and dates are stated ("tested with Espresso 3.x on API 34, May 2026").
- [ ] Feature claims are checked against the current official docs; each has a link.
- [ ] No claim of "best", "fastest" or "most stable" without a measurement and its method.
- [ ] Screenshots and logs contain no secrets, internal names or personal data.
- [ ] Trademarks and product names are spelled correctly.
- [ ] Disclose affiliations and sponsored content.
- [ ] Code and text copied from other sources is credited and licensed for reuse.

## Distribution (optional)

- Meta description: one sentence with the main keyword and the benefit.
- A short intro for social posts: the problem plus one surprising finding, then the link.
- Keep a changelog line at the bottom for updates ("Updated 2026-11: added Compose notes").
