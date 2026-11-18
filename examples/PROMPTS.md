# Example prompts

<!-- Generated from examples/prompts.json by tools/build_catalog.py - do not edit by hand. -->

349 things you can say to your AI coding agent, for all 106 skills. Install a skill ([guide](../GUIDE.md)), then just ask: the agent loads the skill when your request matches its description. To force a skill, start with *"Use the &lt;skill-name&gt; skill: …"*.

**Categories:** [Hub tools](#hub-tools) · [Android: UI tests & logcat](#android-ui-tests--logcat) · [ADB: connect, control & debug Android devices](#adb-connect-control--debug-android-devices) · [Gradle: Android setup, diagnosis & tests](#gradle-android-setup-diagnosis--tests) · [Repositories: read & document](#repositories-read--document) · [GitLab: CI/CD pipelines](#gitlab-cicd-pipelines) · [Writing: blog, CV & docs](#writing-blog-cv--docs) · [Images: pixels & description](#images-pixels--description) · [Video: frames, pixels & description](#video-frames-pixels--description) · [Testing: unit tests & reports](#testing-unit-tests--reports) · [Shell: PowerShell on Windows](#shell-powershell-on-windows) · [Learning: Python tutor & interview notes](#learning-python-tutor--interview-notes) · [YouTube: lecture overviews (study & tech only)](#youtube-lecture-overviews-study--tech-only) · [AI efficiency: save tokens & cost](#ai-efficiency-save-tokens--cost) · [AI agents: MCP, tools, evals & RAG](#ai-agents-mcp-tools-evals--rag) · [Playwright: E2E tests, debugging, CI & browser agent](#playwright-e2e-tests-debugging-ci--browser-agent) · [Robot Framework: suites, libraries, results & CI](#robot-framework-suites-libraries-results--ci) · [UI Automator: Android UI tests in Kotlin & Java](#ui-automator-android-ui-tests-in-kotlin--java) · [Git: getting started](#git-getting-started) · [Git: branching & merging](#git-branching--merging) · [Git: remotes & collaboration](#git-remotes--collaboration) · [Git: power tools](#git-power-tools) · [Git: customization & hooks](#git-customization--hooks) · [Git: internals](#git-internals) · [Git: other systems & APIs](#git-other-systems--apis) · [Git: full reference](#git-full-reference)

## Hub tools

Install the whole category: `--plugin hub-tools`

### Contribute a skill to the hub

[`contribute-skill`](../skills/generic/hub/contribute-skill/SKILL.md) · install: `--skill contribute-skill`

- “Add a new skill called docker-compose-basics to skill-hub.”
- “validate_skills.py says my skill is 'not listed in any plugin'. How do I fix it?”
- “Create a new plugin category in skill-hub for Kubernetes skills.”

### Find & install hub skills

[`find-skills`](../skills/generic/hub/find-skills/SKILL.md) · install: `--skill find-skills`

- “Is there a skill in skill-hub for git submodules? Which plugin has it?”
- “What skills does skill-hub offer for working with Git remotes?”
- “Find me a skill that helps with resolving merge conflicts and install it for this project.”

### Skill orchestrator

[`skill-orchestrator`](../skills/generic/hub/skill-orchestrator/SKILL.md) · install: `--skill skill-orchestrator`

- “Which of my installed skills should I use to analyse this logcat and write a bug report?”
- “Chain the right skills to read this repo and then write a blog post about it.”
- “Check that the skills I need for Android UI testing have everything they need installed.”
- “Plan this job step by step across skills and keep track of the results as we go.”

### Skill router

[`skill-router`](../skills/generic/hub/skill-router/SKILL.md) · install: `--skill skill-router`

- “Which of my skills fits this request: my app keeps crashing after the last update?”
- “Break this down and pick the right skills: analyse the logcat, then write up a bug report for the team.”
- “Before you start, check what you need from me and which installed skills apply to this task.”
- “I'm not sure which skill to use for this. Route it for me.”

### Skillforge: PDF to skills

[`skillforge`](../skills/generic/hub/skillforge/SKILL.md) · install: `--skill skillforge`

- “Turn this Kubernetes handbook PDF into Agent Skills.”
- “Generate skills only for 'backup, restore, replication' from postgres-manual.pdf.”
- “Show me the plan of skills skillforge would create from book.pdf before writing anything.”

### URL to skill: build a skill from a web page

[`url-to-skill`](../skills/generic/hub/url-to-skill/SKILL.md) · install: `--skill url-to-skill`

- “Create a skill from https://docs.python.org/3/library/json.html and save it for later.”
- “Turn the docs under https://docs.example.com/cli/ into one skill called example-cli.”
- “Refresh the skill we generated from that web page last month.”
- “Save this internal wiki page as a skill: http://wiki.corp.local/build-guide”

## Android: UI tests & logcat

Install the whole category: `--plugin android-automation`

### Android logcat analyzer

[`android-logcat-analyzer`](../skills/testing/aaos-testing/android-logcat-analyzer/SKILL.md) · install: `--skill android-logcat-analyzer`

- “Here's logcat.txt from the failed test run. Why did the app crash?”
- “The app froze and then closed on my phone. It's still plugged in, can you check the device log?”
- “Find all the ANRs and service crashes for com.example.player in this bugreport zip.”
- “Our head unit keeps restarting the media service. What does this logcat say?”

### Android UIAutomator dump to locators

[`android-uiautomator-locators`](../skills/testing/aaos-testing/android-uiautomator-locators/SKILL.md) · install: `--skill android-uiautomator-locators`

- “Here's window_dump.xml from our head unit. Generate a JSON with keyword names and resource ids for our tests.”
- “Convert all the window_dump.xml files in dumps/ into locator JSON files in tests/locators.”
- “Dump the current screen from the connected device and generate the locator JSON.”
- “This Compose screen has no resource-ids. Give me the best locators you can from this uiautomator dump.”

## ADB: connect, control & debug Android devices

Install the whole category: `--plugin adb-tools`

### adb debugging: logcat, dumpsys, bug reports, snapshots

[`adb-debug`](../skills/external-tools/adb/adb-debug/SKILL.md) · install: `--skill adb-debug`

- “Show me the logcat errors from com.example.app and save them to a file.”
- “My app crashed on the device. Capture the crash log and tell me what happened.”
- “Create a bug report and a memory and graphics snapshot of my app.”
- “Run the instrumented test CartTest#totalIsSummed through adb and show the result.”

### adb device control: apps, files, screen, settings

[`adb-device-control`](../skills/external-tools/adb/adb-device-control/SKILL.md) · install: `--skill adb-device-control`

- “Install app-debug.apk on my connected phone and start it.”
- “Take a screenshot and a 20 second screen recording of the device.”
- “Pull the Download folder report.pdf from the phone to my computer.”
- “Grant the camera permission to com.example.app and show its version and permissions.”

### adb setup, USB and wireless connection, troubleshooting

[`adb-connect`](../skills/external-tools/adb/adb-connect/SKILL.md) · install: `--skill adb-connect`

- “adb devices shows my phone as unauthorized. How do I fix it?”
- “Pair my Android 14 phone with adb over Wi-Fi.”
- “adb is not recognized on Windows. Install it and get my device connected.”
- “adb says more than one device/emulator. Help me pick the right one.”

### adb: command reference, safety check and central script

[`adb-tool`](../skills/external-tools/adb/adb-tool/SKILL.md) · install: `--skill adb-tool`

- “Which adb command copies a file from my phone to the computer, and is it safe to run?”
- “List every adb command that can delete data or reboot the device.”
- “Run adb shell pm clear on my test app, but check the risk first.”
- “Check my adb setup and tell me what is wrong.”

## Gradle: Android setup, diagnosis & tests

Install the whole category: `--plugin gradle-tools`

### Gradle for Android: setup, diagnosis, libraries and testing

[`gradle-android`](../skills/external-tools/gradle/gradle-android/SKILL.md) · install: `--skill gradle-android`

- “My Android build fails with 'Unsupported class file major version 65'. Find out why and fix it.”
- “Check my Gradle setup: JDK, wrapper, AGP and Kotlin versions, and SDK path.”
- “Add Retrofit to the app module using the version catalog.”
- “Run only the CartTest.totalIsSummed unit test and tell me where the report is.”
- “Here is my Gradle build log: why did the sync fail and what is the fix?”

## Repositories: read & document

Install the whole category: `--plugin repo-tools`

### Repo walkthrough and architecture diagram

[`repo-architecture`](../skills/development/repo/repo-architecture/SKILL.md) · install: `--skill repo-architecture`

- “Make an architecture diagram of this repo as ARCHITECTURE.md and an HTML page.”
- “Give me a walkthrough of this codebase: what the main parts are, how they depend on each other and what to read first.”
- “Draw a component diagram for https://github.com/owner/project and explain the main request flow.”
- “I'm onboarding onto this repo. Prepare an architecture overview I can share with the team.”

### Repository deep read to LEARNINGS.md

[`repo-learnings`](../skills/development/repo/repo-learnings/SKILL.md) · install: `--skill repo-learnings`

- “Read this whole repo, every folder and file, and write a learnings .md so I understand how it works.”
- “I just joined this project. Go through the codebase deeply and create an onboarding document.”
- “Clone https://github.com/owner/project and document what you learn: architecture, how to build it, key files and gotchas.”
- “Study the src and docs folders line by line and give me a LEARNINGS.md.”

## GitLab: CI/CD pipelines

Install the whole category: `--plugin gitlab-ci-tools`

### GitLab CI debugging

[`gitlab-ci-debugging`](../skills/development/gitlab-ci/gitlab-ci-debugging/SKILL.md) · install: `--skill gitlab-ci-debugging`

- “My GitLab job says it's stuck because the project doesn't have any runners online. Why?”
- “Here's the job log. Why did it fail with exit code 137?”
- “My pipeline shows 'Pipeline will not run for the selected trigger'. What's wrong with my rules?”

### GitLab CI optimization

[`gitlab-ci-optimization`](../skills/development/gitlab-ci/gitlab-ci-optimization/SKILL.md) · install: `--skill gitlab-ci-optimization`

- “Our GitLab pipeline takes 40 minutes. How can we speed it up?”
- “The cache doesn't seem to help in our pipeline. Can you tune it?”
- “We're burning CI minutes on duplicate pipelines. How do I cut them?”

### GitLab CI pipeline authoring

[`gitlab-ci-pipeline-authoring`](../skills/development/gitlab-ci/gitlab-ci-pipeline-authoring/SKILL.md) · install: `--skill gitlab-ci-pipeline-authoring`

- “Create a .gitlab-ci.yml that builds, tests and deploys my Node app.”
- “Add a job that only runs on merge requests when files in src/ change.”
- “Split our huge .gitlab-ci.yml into includes and reusable templates.”

## Writing: blog, CV & docs

Install the whole category: `--plugin writing-tools`

### Professional writing: blog, CV, docs

[`professional-writing`](../skills/generic/writing/professional-writing/SKILL.md) · install: `--skill professional-writing`

- “Help me write a blog post comparing test tools for Android: Espresso, UI Automator and Appium.”
- “Here's my CV and a job post. Tailor my CV to this role without making anything up.”
- “Review my CV and tell me the top 3 things to fix.”
- “Draft a README and a how-to guide for my project.”

## Images: pixels & description

Install the whole category: `--plugin image-tools`

### Image inspector: pixels and description

[`image-inspector`](../skills/testing/tools/image-inspector/SKILL.md) · install: `--skill image-inspector`

- “Describe this screenshot.png for me: size, main colours and what's on it.”
- “What is the exact hex colour of the pixel at 120,48 in banner.jpg?”
- “Give me the dominant colour palette of logo.png and tell me if it has a transparent background.”
- “Export every pixel of icon.png to a CSV and read the text in scan.jpg.”
- “Where is play_icon.png on this screenshot? Give me the tap coordinates.”
- “Compare after.png with before.png and show me what changed, ignoring the clock.”

## Video: frames, pixels & description

Install the whole category: `--plugin video-tools`

### Video inspector: frames, pixels and description

[`video-inspector`](../skills/testing/tools/video-inspector/SKILL.md) · install: `--skill video-inspector`

- “Analyse recording.mp4 and describe what happens in it, with a timeline.”
- “Split demo.mp4 into frames, one every 2 seconds, and save them as PNG.”
- “Did the screen go black or freeze anywhere in headunit_test.mp4?”
- “Track the colour of the LED at pixel 50,900 in boot.mp4 over time.”
- “Extract the frame at 0:12.5 from clip.mp4 and give me its pixels as CSV.”

## Testing: unit tests & reports

Install the whole category: `--plugin testing-tools`

### Kotlin unit tests: class/method-wise testing, verification and HTML report

[`kotlin-unit-test`](../skills/testing/libs/kotlin-unit-test/SKILL.md) · install: `--skill kotlin-unit-test`

- “Write unit tests for every method of OrderService.kt and run them.”
- “Run the Kotlin tests for class PriceCalculator and give me an HTML report.”
- “Which methods in this Kotlin project have no tests, and are the existing tests actually asserting anything?”
- “Unit test our Appium LoginPage page object without a device.”
- “Check whether the tests for CartRepository would catch a bug (mutation check).”

### Python unit tests: write, run, diagnose and suggest fixes

[`python-unit-test`](../skills/testing/libs/python-unit-test/SKILL.md) · install: `--skill python-unit-test`

- “Write unit tests for every function in utils.py and run them.”
- “Unit test parser.py and suggest a fix for whatever fails.”
- “Why does test_billing.py fail? Show me the bug and the fix.”
- “Which functions in this .py file have no tests, and are the existing tests asserting anything?”

## Shell: PowerShell on Windows

Install the whole category: `--plugin shell-tools`

### PowerShell Commands for Agents

[`powershell-commands`](../skills/external-tools/powershell/powershell-commands/SKILL.md) · install: `--skill powershell-commands`

- “This `git add . && git commit` fails in PowerShell with a token '&&' error. How do I run it?”
- “Translate this bash one-liner to PowerShell: grep -rn TODO src | wc -l”
- “Write a PowerShell command to find the 10 biggest files under C:\src and show their sizes in MB.”
- “My PowerShell script writes UTF-16 files and the other tool can't read them. Fix the encoding.”

## Learning: Python tutor & interview notes

Install the whole category: `--plugin learning-tools`

### Python tutor: explain a file and make interview notes

[`python-tutor`](../skills/generic/learning/python-tutor/SKILL.md) · install: `--skill python-tutor`

- “Explain this Python file to me like I'm a beginner, then go deeper, and make me an HTML study page.”
- “I have a Python interview next week. Use utils.py to prepare notes and questions for me.”
- “Walk me through app.py line by line and tell me which concepts I should revise.”
- “Make interview-prep notes in HTML for every .py file in this folder.”

## YouTube: lecture overviews (study & tech only)

Install the whole category: `--plugin youtube-tools`

### YouTube lecture overview: link to audio, text and HTML (study and tech only)

[`yt-lecture-overview`](../skills/generic/youtube/yt-lecture-overview/SKILL.md) · install: `--skill yt-lecture-overview`

- “Give me an overview of this lecture as an HTML page: https://www.youtube.com/watch?v=aircAruvnKk”
- “Make study notes and a transcript from this YouTube tutorial link, with a timeline and review questions.”
- “Extract the audio from this lecture, turn the speech into text and make me an overview with the audio analysis.”
- “Only process 10:00 to 25:00 of this 2-hour course video and summarise what that part covers.”
- “Check whether my machine is ready to turn YouTube lecture audio into text, and tell me what to install.”

## AI efficiency: save tokens & cost

Install the whole category: `--plugin ai-efficiency-tools`

### AI token saver: audit a project and spend fewer tokens

[`ai-token-saver`](../skills/generic/ai-efficiency/ai-token-saver/SKILL.md) · install: `--skill ai-token-saver`

- “I keep hitting my AI usage limit. Audit this repo and tell me what to exclude.”
- “How do I reduce token usage and cost when coding with an AI IDE?”
- “My chat context is full and answers got worse. How do I restart without losing progress?”

### Context engineering: one central context for every agent

[`context-engineering`](../skills/generic/ai-efficiency/context-engineering/SKILL.md) · install: `--skill context-engineering`

- “My repo has CLAUDE.md, GEMINI.md and Copilot instructions that disagree. Centralize them into one source of truth.”
- “Set up a context engineering approach for this project so every AI agent loads the same short brief.”
- “Check how much context my instruction files send on every request and split what is too large.”

### Skill token meter: how many tokens each skill saves

[`skill-token-meter`](../skills/generic/ai-efficiency/skill-token-meter/SKILL.md) · install: `--skill skill-token-meter`

- “How many tokens did the yt-lecture-overview skill save on that last task?”
- “Track how many tokens every skill saves me in this session and show a report at the end.”
- “Which of my installed skills cost the most tokens every session?”
- “Compare these two session logs, one with the skill and one without, and record the savings.”

## AI agents: MCP, tools, evals & RAG

Install the whole category: `--plugin ai-agent-tools`

### Agent tool design: names, schemas and errors models use well

[`agent-tool-design`](../skills/development/ai-agents/agent-tool-design/SKILL.md) · install: `--skill agent-tool-design`

- “Review these function calling definitions; the model keeps choosing the wrong tool.”
- “Design the tools for a support agent that can look up orders and issue refunds.”
- “Lint tools.json and improve the descriptions and parameter schemas.”

### LLM evals: test sets, scoring and regression checks

[`llm-evals`](../skills/development/ai-agents/llm-evals/SKILL.md) · install: `--skill llm-evals`

- “Set up an eval set for our summarization prompt and score the current outputs.”
- “Compare the new prompt version against last week's baseline and list regressions.”
- “Add an LLM eval to CI that fails the build if the pass rate drops below 90%.”

### MCP server builder: create, probe and debug MCP servers

[`mcp-server-builder`](../skills/development/ai-agents/mcp-server-builder/SKILL.md) · install: `--skill mcp-server-builder`

- “Build an MCP server in Python that exposes our internal notes search as a tool.”
- “My MCP server starts but the agent shows no tools. Probe it and tell me what is wrong.”
- “Wrap this REST API as an MCP server in TypeScript and test it before I add it to my agent.”

### RAG pipeline: chunk, retrieve, ground and evaluate

[`rag-pipeline`](../skills/development/ai-agents/rag-pipeline/SKILL.md) · install: `--skill rag-pipeline`

- “Build a RAG pipeline so users can chat with our Markdown docs.”
- “Our RAG bot answers without using the docs. Find out if retrieval is the problem.”
- “Chunk the docs folder and measure recall@5 for these labelled questions.”

## Playwright: E2E tests, debugging, CI & browser agent

Install the whole category: `--plugin playwright-tools`

### Playwright debugging: failing and flaky tests

[`playwright-debugging`](../skills/testing/playwright/playwright-debugging/SKILL.md) · install: `--skill playwright-debugging`

- “Our Playwright tests pass locally but fail in CI. Here is results.json, find out why.”
- “Which Playwright tests are flaky in this report and what is causing them?”
- “This test times out on the Pay button; read the trace and fix it.”

### Playwright in CI: pipelines, sharding and reports

[`playwright-ci`](../skills/testing/playwright/playwright-ci/SKILL.md) · install: `--skill playwright-ci`

- “Add Playwright to GitHub Actions with 4 shards and one merged HTML report.”
- “Generate a GitLab CI job for our Playwright suite using the right Docker image.”
- “Our Playwright run takes 40 minutes in Jenkins; split it into parallel shards.”

### Playwright MCP: let the agent use a browser, then keep it as a test

[`playwright-mcp-browser`](../skills/testing/playwright/playwright-mcp-browser/SKILL.md) · install: `--skill playwright-mcp-browser`

- “Open our staging site, sign in as the test user and check that checkout works.”
- “Reproduce this bug report in the browser and tell me what errors show in the console.”
- “Click through the new settings page and turn what you did into a Playwright test.”

### Playwright test authoring: resilient E2E tests that fit your team

[`playwright-test-authoring`](../skills/testing/playwright/playwright-test-authoring/SKILL.md) · install: `--skill playwright-test-authoring`

- “Write Playwright tests for our login and checkout flow using our data-qa attributes.”
- “Audit our Playwright suite for flaky patterns and fix the worst ones.”
- “Set up Playwright in this repo with login reuse, staging and production base URLs, and an @smoke tag.”

### Playwright upgrade: breaking changes, affected code, steps

[`playwright-upgrade`](../skills/testing/playwright/playwright-upgrade/SKILL.md) · install: `--skill playwright-upgrade`

- “Upgrade our Playwright from 1.48 to the latest version and tell me what will break.”
- “We bumped Playwright and CI now fails with Node and Docker errors; fix the upgrade.”
- “Which removed Playwright APIs does this repo still use?”

## Robot Framework: suites, libraries, results & CI

Install the whole category: `--plugin robotframework-tools`

### Robot Framework authoring: modern 7.x syntax and an audit

[`robotframework-test-authoring`](../skills/testing/robot-framework/robotframework-test-authoring/SKILL.md) · install: `--skill robotframework-test-authoring`

- “Write Robot Framework tests for our login and checkout using the Browser library.”
- “Modernise these old .robot files to Robot Framework 7 syntax (VAR, IF, RETURN).”
- “Move the passwords in our robot variables to secret variables from the environment.”

### Robot Framework in CI: run, rerun, parallelise, report

[`robotframework-ci`](../skills/testing/robot-framework/robotframework-ci/SKILL.md) · install: `--skill robotframework-ci`

- “Add Robot Framework tests to GitHub Actions with a rerun of failed tests.”
- “Run our Robot suite in parallel with pabot in GitLab CI and publish JUnit results.”
- “Create a Jenkinsfile for our Robot Framework tests with the Browser library.”

### Robot Framework libraries: Python keywords done right

[`robotframework-libraries`](../skills/testing/robot-framework/robotframework-libraries/SKILL.md) · install: `--skill robotframework-libraries`

- “Write a Python keyword library for our Orders API to use in Robot Framework.”
- “Review our custom Robot Framework library: types, docs and logging.”
- “Generate Markdown documentation for this Robot library with Libdoc.”

### Robot Framework results: failures, flaky tests and slow keywords

[`robotframework-results`](../skills/testing/robot-framework/robotframework-results/SKILL.md) · install: `--skill robotframework-results`

- “Our Robot Framework run failed in CI; here is output.xml, tell me why.”
- “Which Robot tests are flaky? Compare output.xml with the rerun output.”
- “Why did our Robot suite get so slow? Find the slowest keywords.”

## UI Automator: Android UI tests in Kotlin & Java

Install the whole category: `--plugin uiautomator-tools`

### UI Automator migration and audit (Kotlin and Java)

[`uiautomator-migration`](../skills/testing/uiautomator/uiautomator-migration/SKILL.md) · install: `--skill uiautomator-migration`

- “Migrate our UI Automator tests from UiSelector and UiScrollable to the current API.”
- “Audit the androidTest folder for flaky UI Automator code and deprecated calls.”
- “We bumped uiautomator to 2.4.1 and onView { } no longer compiles. Fix our Kotlin tests.”
- “Convert this Java test that uses UiObject and Thread.sleep to By, Until and UiObject2.”

### UI Automator test authoring (Kotlin and Java)

[`uiautomator-test-authoring`](../skills/testing/uiautomator/uiautomator-test-authoring/SKILL.md) · install: `--skill uiautomator-test-authoring`

- “Set up UI Automator in our Android app and write a Kotlin test that signs in and checks the home screen.”
- “Write a Java UI Automator test that opens Settings, turns on Do Not Disturb and checks it is on.”
- “Generate a page object for this screen from locators/login.locators.json, in Kotlin with the new uiAutomator DSL.”
- “Our test needs to accept the location permission dialog and then tap a notification. How do I do that with UI Automator?”
- “Create a Macrobenchmark and a Baseline Profile generator for app startup using UI Automator.”

### UI Automator: run tests and debug failures

[`uiautomator-run-debug`](../skills/testing/uiautomator/uiautomator-run-debug/SKILL.md) · install: `--skill uiautomator-run-debug`

- “Run only LoginTest#signIn from our UI Automator suite on the emulator and tell me why it fails.”
- “Here's the am instrument output from CI. Which tests failed and why?”
- “Our UI Automator tests fail with UiAutomationService already registered. What's wrong?”
- “Shard the instrumented tests across 4 devices and summarise the JUnit results.”

## Git: getting started

Install the whole category: `--plugin git-getting-started`

### Basic Snapshotting

[`git-basic-snapshotting`](../skills/development/git-getting-started/git-basic-snapshotting/SKILL.md) · install: `--skill git-basic-snapshotting`

- “Explain the basic add, status, diff and commit workflow in Git.”
- “How do I remove a file from Git but keep it on disk?”
- “Rename a file so Git tracks the move.”

### First-Time Git Setup

[`git-first-time-git-setup`](../skills/development/git-getting-started/git-first-time-git-setup/SKILL.md) · install: `--skill git-first-time-git-setup`

- “I just installed Git. What should I configure first?”
- “Set my Git name and email globally.”
- “Make VS Code my default Git editor and set the default branch name to main.”

### Getting a Git Repository

[`git-getting-a-git-repository`](../skills/development/git-getting-started/git-getting-a-git-repository/SKILL.md) · install: `--skill git-getting-a-git-repository`

- “Turn this existing folder into a Git repository.”
- “Clone https://github.com/libgit2/libgit2 into a folder named mylibgit.”
- “What's the difference between git init and git clone?”

### Getting Help

[`git-getting-help`](../skills/development/git-getting-started/git-getting-help/SKILL.md) · install: `--skill git-getting-help`

- “How do I see the manual page for git commit?”
- “Show me a quick summary of the options for git add.”
- “Where can I get help with Git commands offline?”

### Git Aliases

[`git-aliases`](../skills/development/git-getting-started/git-aliases/SKILL.md) · install: `--skill git-aliases`

- “Create a git alias so 'git st' runs git status.”
- “Make a 'git last' command that shows the last commit.”
- “How do I create a git alias that runs an external shell command?”

### Installing Git

[`git-installing-git`](../skills/development/git-getting-started/git-installing-git/SKILL.md) · install: `--skill git-installing-git`

- “How do I install Git on Ubuntu?”
- “Install the latest Git on my Mac.”
- “I want to build Git from source. What do I need?”

### Recording Changes to the Repository

[`git-recording-changes-to-the-repository`](../skills/development/git-getting-started/git-recording-changes-to-the-repository/SKILL.md) · install: `--skill git-recording-changes-to-the-repository`

- “How do I stage only some files and commit them?”
- “Make Git ignore all .log files and the build/ folder.”
- “Show me what I've staged versus what I've changed but not staged.”

### Setup and Config

[`git-setup-and-config`](../skills/development/git-getting-started/git-setup-and-config/SKILL.md) · install: `--skill git-setup-and-config`

- “Show me all my Git config settings and where each one comes from.”
- “What's the difference between --system, --global and --local config in Git?”
- “How do I change the editor Git opens for commit messages?”

### Tagging

[`git-tagging`](../skills/development/git-getting-started/git-tagging/SKILL.md) · install: `--skill git-tagging`

- “Create an annotated tag v1.2.0 with a message and push it.”
- “List all tags that start with v2.”
- “Delete a tag both locally and on the remote.”

### Undoing Things

[`git-undoing-things`](../skills/development/git-getting-started/git-undoing-things/SKILL.md) · install: `--skill git-undoing-things`

- “I forgot to add a file to my last commit. How do I fix it?”
- “Unstage a file I accidentally added.”
- “Throw away my local changes to config.yml.”

### Viewing the Commit History

[`git-viewing-the-commit-history`](../skills/development/git-getting-started/git-viewing-the-commit-history/SKILL.md) · install: `--skill git-viewing-the-commit-history`

- “Show the last 5 commits with the diffs.”
- “Find the commits that added or removed the string 'getUserToken'.”
- “Show a one-line graph of the history of all branches.”

## Git: branching & merging

Install the whole category: `--plugin git-branching`

### Advanced Merging

[`git-advanced-merging`](../skills/development/git-branching/git-advanced-merging/SKILL.md) · install: `--skill git-advanced-merging`

- “Abort this merge, it went wrong.”
- “During a merge conflict, take their version of every conflicting file.”
- “Undo a merge commit that was already pushed.”

### Basic Branching and Merging

[`git-basic-branching-and-merging`](../skills/development/git-branching/git-basic-branching-and-merging/SKILL.md) · install: `--skill git-basic-branching-and-merging`

- “Create a hotfix branch, fix the bug, and merge it back into main.”
- “I got 'CONFLICT (content): Merge conflict in index.html'. What do I do?”
- “What's the difference between a fast-forward merge and a merge commit?”

### Branch Management

[`git-branch-management`](../skills/development/git-branching/git-branch-management/SKILL.md) · install: `--skill git-branch-management`

- “List the branches already merged into main so I can delete them.”
- “Rename my local branch from 'feat' to 'feature/login'.”
- “Show each branch with its last commit.”

### Branches in a Nutshell

[`git-branches-in-a-nutshell`](../skills/development/git-branching/git-branches-in-a-nutshell/SKILL.md) · install: `--skill git-branches-in-a-nutshell`

- “Explain how Git branches and HEAD actually work.”
- “Create a branch called testing and switch to it.”
- “Show which commit each branch points to.”

### Rebasing

[`git-rebasing`](../skills/development/git-branching/git-rebasing/SKILL.md) · install: `--skill git-rebasing`

- “Rebase my feature branch onto the latest main without a merge commit.”
- “Move a branch that was based on 'server' so it sits directly on main using --onto.”
- “When should I avoid rebasing? I already pushed my branch.”

### Remote Branches

[`git-remote-branches`](../skills/development/git-branching/git-remote-branches/SKILL.md) · install: `--skill git-remote-branches`

- “Make my local branch track origin/develop.”
- “Delete the branch 'old-feature' on the remote.”
- “Show how far ahead of or behind its upstream each of my branches is.”

### Rerere

[`git-rerere`](../skills/development/git-branching/git-rerere/SKILL.md) · install: `--skill git-rerere`

- “Make Git remember how I resolved conflicts so it reapplies the fix next time.”
- “Turn on rerere and show me what it has recorded.”
- “I keep resolving the same conflict on every rebase. How can Git automate that?”

## Git: remotes & collaboration

Install the whole category: `--plugin git-collaboration`

### Contributing to a Project

[`git-distributed-git-contributing-to-a-project`](../skills/development/git-collaboration/git-distributed-git-contributing-to-a-project/SKILL.md) · install: `--skill git-distributed-git-contributing-to-a-project`

- “What makes a good commit message?”
- “How do I contribute to a project by sending patches by email?”
- “Squash my topic branch into one commit before sending it upstream.”

### Contributing to a Project

[`git-github-contributing-to-a-project`](../skills/development/git-collaboration/git-github-contributing-to-a-project/SKILL.md) · install: `--skill git-github-contributing-to-a-project`

- “Fork a GitHub project, make a change, and open a pull request.”
- “Update my pull request after the maintainer asked for changes.”
- “Sync my fork with the upstream repository.”

### Credential Storage

[`git-credential-storage`](../skills/development/git-collaboration/git-credential-storage/SKILL.md) · install: `--skill git-credential-storage`

- “Stop Git asking for my password on every push.”
- “Cache my Git credentials for 1 hour.”
- “Which credential helper should I use on Windows or macOS?”

### Generating Your SSH Public Key

[`git-generating-your-ssh-public-key`](../skills/development/git-collaboration/git-generating-your-ssh-public-key/SKILL.md) · install: `--skill git-generating-your-ssh-public-key`

- “Generate an SSH key to use with Git.”
- “Do I already have an SSH key? Where is it stored?”
- “How do I give my SSH public key to the Git server admin?”

### Getting Git on a Server

[`git-getting-git-on-a-server`](../skills/development/git-collaboration/git-getting-git-on-a-server/SKILL.md) · install: `--skill git-getting-git-on-a-server`

- “Create a bare repository to put on my server.”
- “Set up a shared Git repo on a Linux server that my team can push to.”
- “Make a server repository group-writable for all developers.”

### Git Daemon

[`git-daemon`](../skills/development/git-collaboration/git-daemon/SKILL.md) · install: `--skill git-daemon`

- “Serve my repositories read-only with git daemon.”
- “Run git daemon as a systemd service.”
- “Allow anonymous cloning of a repository over git://.”

### GitWeb

[`git-gitweb`](../skills/development/git-collaboration/git-gitweb/SKILL.md) · install: `--skill git-gitweb`

- “Set up GitWeb to browse my repositories in a web browser.”
- “Run a quick GitWeb instance with git instaweb.”
- “Install GitWeb on Apache for all repos in /srv/git.”

### Maintaining a Project

[`git-distributed-git-maintaining-a-project`](../skills/development/git-collaboration/git-distributed-git-maintaining-a-project/SKILL.md) · install: `--skill git-distributed-git-maintaining-a-project`

- “Apply a patch someone emailed me with git am.”
- “Review the changes a contributor's branch introduces before I merge it.”
- “Create a release tarball and a shortlog for my project's release notes.”

### Maintaining a Project

[`git-github-maintaining-a-project`](../skills/development/git-collaboration/git-github-maintaining-a-project/SKILL.md) · install: `--skill git-github-maintaining-a-project`

- “Check out a GitHub pull request locally to test it.”
- “Add collaborators to my GitHub repository.”
- “How do I use pull request refs to fetch all open PRs?”

### Scripting GitHub

[`git-scripting-github`](../skills/development/git-collaboration/git-scripting-github/SKILL.md) · install: `--skill git-scripting-github`

- “Use the GitHub API to comment on an issue.”
- “Set the commit status on GitHub from a script.”
- “Get notified with a webhook when someone pushes to my repo.”

### Setting Up the Server

[`git-setting-up-the-server`](../skills/development/git-collaboration/git-setting-up-the-server/SKILL.md) · install: `--skill git-setting-up-the-server`

- “Set up a git user on my server that accepts SSH keys from my team.”
- “Restrict the git user so it can only run Git commands (git-shell).”
- “Add a new developer's public key to my Git server.”

### Smart HTTP

[`git-smart-http`](../skills/development/git-collaboration/git-smart-http/SKILL.md) · install: `--skill git-smart-http`

- “Set up Smart HTTP for Git with Apache.”
- “Configure git-http-backend so pushes over HTTP require a password.”
- “Host Git over HTTPS on my own server.”

### The Protocols

[`git-the-protocols`](../skills/development/git-collaboration/git-the-protocols/SKILL.md) · install: `--skill git-the-protocols`

- “Should I use SSH or HTTPS to host my Git repository?”
- “Explain the local, HTTP, SSH and git:// protocols and their pros and cons.”
- “Clone a repository from a shared network folder.”

### Working with Remotes

[`git-working-with-remotes`](../skills/development/git-collaboration/git-working-with-remotes/SKILL.md) · install: `--skill git-working-with-remotes`

- “List the remotes of this repository with their URLs.”
- “Add a second remote called upstream and fetch from it.”
- “Rename the remote 'origin' to 'github'.”

## Git: power tools

Install the whole category: `--plugin git-power-tools`

### Bundling

[`git-bundling`](../skills/development/git-power-tools/git-bundling/SKILL.md) · install: `--skill git-bundling`

- “Send my repository to someone without network access.”
- “Create a git bundle with only the last 10 commits.”
- “Clone from a .bundle file.”

### Debugging with Git

[`git-debugging-with-git`](../skills/development/git-power-tools/git-debugging-with-git/SKILL.md) · install: `--skill git-debugging-with-git`

- “Use git bisect to find which commit introduced a bug.”
- “Who last changed lines 10 to 20 of app.py?”
- “Automate git bisect with a test script.”

### Interactive Staging

[`git-interactive-staging`](../skills/development/git-power-tools/git-interactive-staging/SKILL.md) · install: `--skill git-interactive-staging`

- “Stage only some of the changes in a file.”
- “Use git add -p to split my changes into two commits.”
- “Walk me through git add -i.”

### Replace

[`git-replace`](../skills/development/git-power-tools/git-replace/SKILL.md) · install: `--skill git-replace`

- “Make Git treat one commit as if it were another with git replace.”
- “Graft old project history onto a shortened repository.”
- “How do I list and delete git replace refs?”

### Reset Demystified

[`git-reset-demystified`](../skills/development/git-power-tools/git-reset-demystified/SKILL.md) · install: `--skill git-reset-demystified`

- “Explain the difference between git reset --soft, --mixed and --hard.”
- “Undo my last commit but keep the changes staged.”
- “What's the difference between git reset and git checkout on a file?”

### Revision Selection

[`git-revision-selection`](../skills/development/git-power-tools/git-revision-selection/SKILL.md) · install: `--skill git-revision-selection`

- “What does HEAD~3 versus HEAD^2 mean?”
- “Show the commits on my branch that are not on main.”
- “Use the reflog to find where my branch pointed yesterday.”

### Rewriting History

[`git-rewriting-history`](../skills/development/git-power-tools/git-rewriting-history/SKILL.md) · install: `--skill git-rewriting-history`

- “Change the message of a commit three commits back.”
- “Squash my last 4 commits into one.”
- “Remove a file with a leaked password from the entire Git history.”

### Searching

[`git-searching`](../skills/development/git-power-tools/git-searching/SKILL.md) · install: `--skill git-searching`

- “Search the whole repository for 'TODO' with line numbers.”
- “Find when the function parseConfig was introduced.”
- “Show the history of a single function in a file.”

### Signing Your Work

[`git-signing-your-work`](../skills/development/git-power-tools/git-signing-your-work/SKILL.md) · install: `--skill git-signing-your-work`

- “Sign my commits with GPG.”
- “Create a signed tag and verify it.”
- “Make Git sign every commit automatically.”

### Stashing and Cleaning

[`git-stashing-and-cleaning`](../skills/development/git-power-tools/git-stashing-and-cleaning/SKILL.md) · install: `--skill git-stashing-and-cleaning`

- “I have half-done changes and need to switch branches urgently.”
- “Stash my changes including untracked files, then restore them later.”
- “Remove all untracked files and folders, but show me what will be deleted first.”

### Submodules

[`git-submodules`](../skills/development/git-power-tools/git-submodules/SKILL.md) · install: `--skill git-submodules`

- “Add a library as a git submodule.”
- “Clone a repository together with all its submodules.”
- “Update all submodules to their latest upstream commits.”

## Git: customization & hooks

Install the whole category: `--plugin git-customization`

### An Example Git-Enforced Policy

[`git-an-example-git-enforced-policy`](../skills/development/git-customization/git-an-example-git-enforced-policy/SKILL.md) · install: `--skill git-an-example-git-enforced-policy`

- “Enforce a commit message format on the server with an update hook.”
- “Restrict which users can push to which directories.”
- “Prevent non-fast-forward pushes on the server.”

### Environment Variables

[`git-environment-variables`](../skills/development/git-customization/git-environment-variables/SKILL.md) · install: `--skill git-environment-variables`

- “Which environment variable sets the committer date in Git?”
- “Debug a slow git fetch with GIT_TRACE.”
- “Use a different SSH command for one Git operation.”

### Git Attributes

[`git-attributes`](../skills/development/git-customization/git-attributes/SKILL.md) · install: `--skill git-attributes`

- “Tell Git to treat *.pdf files as binary.”
- “Diff Word documents in Git in a readable way.”
- “Keep a config file's local version during merges with a merge strategy attribute.”

### Git Configuration

[`git-configuration`](../skills/development/git-customization/git-configuration/SKILL.md) · install: `--skill git-configuration`

- “Make Git colorize output and use a custom pager.”
- “Configure core.autocrlf correctly for a team on Windows and Linux.”
- “Set up a global .gitignore and a commit message template.”

### Git Hooks

[`git-hooks`](../skills/development/git-customization/git-hooks/SKILL.md) · install: `--skill git-hooks`

- “Block commits whose message doesn't start with a ticket ID like ABC-123.”
- “Run my test suite before every commit with a pre-commit hook.”
- “Which server-side hooks can reject a push?”

## Git: internals

Install the whole category: `--plugin git-internals`

### Git Objects

[`git-objects`](../skills/development/git-internals/git-objects/SKILL.md) · install: `--skill git-objects`

- “Explain blobs, trees and commits in Git internals.”
- “Create a Git object by hand with hash-object and read it back with cat-file.”
- “Show the tree object of the latest commit.”

### Git References

[`git-references`](../skills/development/git-internals/git-references/SKILL.md) · install: `--skill git-references`

- “How are branches stored inside .git?”
- “Update a branch ref directly with git update-ref.”
- “What is HEAD internally, and what's a symbolic ref?”

### Maintenance and Data Recovery

[`git-maintenance-and-data-recovery`](../skills/development/git-internals/git-maintenance-and-data-recovery/SKILL.md) · install: `--skill git-maintenance-and-data-recovery`

- “I deleted a branch by accident. How do I get it back?”
- “Find and remove a huge file that is bloating my repository.”
- “Recover lost commits with git fsck and the reflog.”

### Packfiles

[`git-packfiles`](../skills/development/git-internals/git-packfiles/SKILL.md) · install: `--skill git-packfiles`

- “Why is my .git folder so big? Explain packfiles.”
- “Inspect the contents of a packfile with git verify-pack.”
- “Run git gc and explain what it does.”

### Plumbing and Porcelain

[`git-plumbing-and-porcelain`](../skills/development/git-internals/git-plumbing-and-porcelain/SKILL.md) · install: `--skill git-plumbing-and-porcelain`

- “What's the difference between plumbing and porcelain commands in Git?”
- “What's inside the .git directory?”
- “Which Git commands are safe to use in scripts?”

### The Refspec

[`git-the-refspec`](../skills/development/git-internals/git-the-refspec/SKILL.md) · install: `--skill git-the-refspec`

- “Explain the refspec +refs/heads/*:refs/remotes/origin/*.”
- “Fetch only the main branch from a remote by default.”
- “Push my local branch to a differently named remote branch.”

### Transfer Protocols

[`git-transfer-protocols`](../skills/development/git-internals/git-transfer-protocols/SKILL.md) · install: `--skill git-transfer-protocols`

- “How does git fetch talk to the server over HTTP?”
- “Explain the dumb versus smart Git transfer protocols.”
- “What happens during git push over SSH (send-pack and receive-pack)?”

## Git: other systems & APIs

Install the whole category: `--plugin git-integrations`

### Git as a Client

[`git-as-a-client`](../skills/development/git-integrations/git-as-a-client/SKILL.md) · install: `--skill git-as-a-client`

- “Use Git with a Subversion repository via git svn.”
- “Push my Git commits back to SVN with git svn dcommit.”
- “Work with a Mercurial or Perforce server from Git.”

### Git in PowerShell

[`git-in-powershell`](../skills/development/git-integrations/git-in-powershell/SKILL.md) · install: `--skill git-in-powershell`

- “Set up posh-git so PowerShell shows Git status in my prompt.”
- “Install posh-git on Windows.”
- “Get Git tab completion in PowerShell.”

### JGit

[`git-jgit`](../skills/development/git-integrations/git-jgit/SKILL.md) · install: `--skill git-jgit`

- “Use JGit to open a repository and read the latest commit in Java.”
- “Clone a repository from Java code.”
- “How do I add JGit to my Maven project?”

### Libgit2

[`git-libgit2`](../skills/development/git-integrations/git-libgit2/SKILL.md) · install: `--skill git-libgit2`

- “Use libgit2 to read a commit in C.”
- “What language bindings exist for libgit2?”
- “Create a commit programmatically with libgit2.”

### Migrating to Git

[`git-migrating-to-git`](../skills/development/git-integrations/git-migrating-to-git/SKILL.md) · install: `--skill git-migrating-to-git`

- “Migrate our SVN repository to Git, keeping history and authors.”
- “Convert a Mercurial repo to Git.”
- “Write a custom importer with git fast-import.”

## Git: full reference

Install the whole category: `--plugin git-reference`

### Pro Git (full reference)

[`git-pro`](../skills/development/git-reference/git-pro/SKILL.md) · install: `--skill git-pro`

- “Explain how Git stores data compared to other version control systems.”
- “Give me an overview of Git's distributed workflows.”
- “What does the Pro Git book say about customizing Git?”
