---
name: git-github-contributing-to-a-project
description: "Contributing to a Project playbook extracted from \"Pro Git\". This is the basic workflow that most GitHub projects use. Use when the user asks about contributing to a project, pull request; or mentions git push, git remote, git fetch, git checkout, git pull, git clone; or hits errors like \"CONFLICT (content): Merge conflict in blink.ino\"."
---

# Contributing to a Project

This is the basic workflow that most GitHub projects use.

_Built from "Pro Git" (pages 177-197) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **contributing to a project** (pull request).
- The user wants to run or understand `git push`.
- The user wants to run or understand `git remote`.
- The user wants to run or understand `git fetch`.
- The user wants to run or understand `git checkout`.
- The user sees an error like `CONFLICT (content): Merge conflict in blink.ino`.
- If you want to contribute to an existing project to which you don’t have push access, you can “fork”

## When NOT to use

- For maintaining a project, use the `git-github-maintaining-a-project` skill instead.
- For contributing to a project, use the `git-distributed-git-contributing-to-a-project` skill instead.
- For maintaining a project, use the `git-distributed-git-maintaining-a-project` skill instead.

## Key concepts

- 4.Push this branch to your GitHub project.
- 7.The project owner merges or closes the Pull Request.
- You can alternatively go to the “Branches” page at `https://github.com/<user>/<project>/branches` to locate your branch and open a new Pull Request from there.
- We also see a list of the commits in our topic branch that are “ahead” of the `master` branch (in this case, just the one) and a unified diff of all the changes that will be made should this branch get merged by the project owner.
- In Pull Request discussion page we can see an example of the project owner both commenting on a line of code and then leaving a general comment in the discussion section.
- Adding commits to an existing Pull Request doesn’t trigger a notification, so once Tony has pushed his corrections he decides to leave a comment to inform the project owner that he made the requested change.
- Most GitHub projects think about Pull Request branches as iterative conversations around a proposed change, culminating in a unified diff that is applied by merging.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- If you absolutely wish to rebase the branch to clean it up, you can certainly do so, but it is highly encouraged to not force push over the branch that the Pull Request is already opened on.
- But your GitHub repository will never be automatically updated by GitHub; this is something that you must do yourself.

## Procedures

### The GitHub Flow

**Goal:** This is the basic workflow that most GitHub projects use.

**Steps:**

1. We will clone it locally, create a topic branch, make the code change and finally push that change back up to GitHub.
   ```bash
   git clone https://github.com/tonychacon/blink ①
   cd blink
   git checkout -b slow-blink ②
   sed -i '' 's/1000/3000/' blink.ino (macOS) ③
   git diff --word-diff ④
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'blink'...
   Switched to a new branch 'slow-blink'
   # If you're on a Linux system, do this instead:
   # $ sed -i 's/1000/3000/' blink.ino ③
   ```
2. Run:
   ```bash
   git commit -a -m 'Change delay to 3 seconds' ⑤
   git push origin slow-blink ⑥
   ```
   Expected output (excerpt):
   ```text
   [slow-blink 5ca509d] Change delay to 3 seconds
    1 file changed, 2 insertions(+), 2 deletions(-)
   Username for 'https://github.com': tonychacon
   Password for 'https://tonychacon@github.com':
   ```

### Advanced Pull Requests

**Goal:** This is an important distinction, because generally the change is suggested before the code is thought to be perfect, which is far more rare with mailing list based patch series contributions.

**Steps:**

1. Let’s go through those steps.
   ```bash
   git remote add upstream https://github.com/schacon/blink ①
   git fetch upstream ②
   git merge upstream/master ③
   vim blink.ino ④
   git add blink.ino
   git commit
   git push origin slow-blink ⑤
   ```
   Expected output (excerpt):
   ```text
   remote: Counting objects: 3, done.
   remote: Compressing objects: 100% (3/3), done.
   Unpacking objects: 100% (3/3), done.
   remote: Total 3 (delta 0), reused 0 (delta 0)
   ```
2. Run:
   ```text
   Writing objects: 100% (6/6), 682 bytes | 0 bytes/s, done.
   Total 6 (delta 2), reused 0 (delta 0)
   To https://github.com/tonychacon/blink
      ef4725c..3c8d735  slower-blink -> slow-blink
   ```

**If it fails:** If your Pull Request becomes out of date or otherwise doesn’t merge cleanly, you will want to fix it so the maintainer can easily merge it.

### GitHub Flavored Markdown

**Goal:** GitHub Flavored Markdown

**Steps:**

1. You can create a task list like this:
   ```text
   - [X] Write the code
   - [ ] Write all the tests
   - [ ] Document the code
   ```
2. To add a snippet of code you have to “fence” it in backticks.
   ```text
   ```java
   for(int i=0 ; i < 5 ; i++)
   {
      System.out.println("i is : " + i);
   }
   ```
   ```
3. The quotes look something like this:
   ```text
   > Whether 'tis Nobler in the mind to suffer
   > The Slings and Arrows of outrageous Fortune,
   How big are these slings and in particular, these arrows?
   ```
4. For instance, you could write something like this:
   ```text
   I :eyes: that :bug: and I :cold_sweat:.
   :trophy: for :microscope: it.
   :+1: and :sparkles: on this :ship:, it's :fire::poop:!
   :clap::tada::panda_face:
   ```

### Keep your GitHub public repository up-to-date

**Goal:** Keep your GitHub public repository up-to-date

**Steps:**

1. In particular, when the original repository has new commits, GitHub informs you by a message like:
   ```text
   This branch is 5 commits behind progit:master.
   ```
2. For example, if you forked from `https://github.com/progit/progit2.git`, you can keep your `master` branch up-to-date like this:
   ```bash
   git checkout master ①
   git pull https://github.com/progit/progit2.git ②
   git push origin master ③
   ```
3. You can automate this work with a bit of configuration:
   ```bash
   git remote add progit https://github.com/progit/progit2.git ①
   git fetch progit ②
   git branch --set-upstream-to=progit/master master ③
   git config --local remote.pushDefault origin ④
   ```
4. Once this is done, the workflow becomes much simpler:
   ```bash
   git checkout master ①
   git pull ②
   git push ③
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git push` | We will clone it locally, create a topic branch, make the code change and finally push that change back up to GitHub. | `git push ③` |
| `git remote` | `③`Set your `master` branch to fetch from the `progit` remote. | `git remote add upstream https://github.com/schacon/blink ①` |
| `git fetch` | Let’s go through those steps. | `git fetch progit ②` |
| `git checkout` | For example, if you forked from `https://github.com/progit/progit2.git`, you can keep your `master` branch up-to-date like this | `git checkout master ①` |
| `git pull` | For example, if you forked from `https://github.com/progit/progit2.git`, you can keep your `master` branch up-to-date like this | `git pull ②` |
| `git clone` | We will clone it locally, create a topic branch, make the code change and finally push that change back up to GitHub. | `git clone https://github.com/tonychacon/blink ①` |
| `git checkout -b` | We will clone it locally, create a topic branch, make the code change and finally push that change back up to GitHub. | `git checkout -b slow-blink ②` |
| `sed -i` | We will clone it locally, create a topic branch, make the code change and finally push that change back up to GitHub. | `sed -i '' 's/1000/3000/' blink.ino (macOS) ③` |
| `git diff --word-diff` | We will clone it locally, create a topic branch, make the code change and finally push that change back up to GitHub. | `git diff --word-diff ④` |
| `git commit -a -m` | We will clone it locally, create a topic branch, make the code change and finally push that change back up to GitHub. | `git commit -a -m 'Change delay to 3 seconds' ⑤` |
| `git merge` | Let’s go through those steps. | `git merge upstream/master ③` |
| `git add` | Let’s go through those steps. | `git add blink.ino` |
| `git commit` | Let’s go through those steps. | `git commit` |
| `git branch --set-upstream-to` | You can automate this work with a bit of configuration | `git branch --set-upstream-to=progit/master master ③` |
| `git config --local` | You can automate this work with a bit of configuration | `git config --local remote.pushDefault origin ④` |

## Decision guide

- This is basically the Integration Manager workflow covered in Integration-Manager Workflow, but instead of using email to communicate and review changes, teams use GitHub’s web based tools.
- We think it’s much nicer to wait 3 seconds instead of 1 in between each state change.
- If you would prefer, you can simply pull the branch down and merge it locally.
- When code is proposed with a Pull Request and the maintainers or community suggest a change, the patch series is generally not re-rolled, but instead the difference is pushed as a new commit to the branch, moving the conversation forward with the context of the previous work intact.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `CONFLICT (content): Merge conflict in blink.ino` | `①`Add the original repository as a remote named `upstream`. |

- **Note:** Historically, the term “fork” has been somewhat negative in context, meaning that someone took an open source project in a different direction, sometimes creating a competing project and splitting the contributors. In GitHub, a “fork” is simply the same project in your own namespace, allowing you to make changes to a project publicly as a way to contribute in a more open manner.
- **Tip:** You can use the official GitHub CLI tool instead of the GitHub web interface for most things. The tool can be used on Windows, macOS, and Linux systems. Go to the GitHub CLI homepage for installation instructions and the manual.
- **Note:** Though Pull Requests are used commonly for public projects like this when the contributor has a complete change ready to be made, it’s also often used in internal projects at the beginning of the development cycle. Since you can keep pushing to the topic branch even after the Pull Request is opened, it’s often opened early and used as a way to iterate on work as a team within a context, rather than opened at the very end of the process.
- **Note:** Not Only Forks It’s important to note that you can also open a Pull Request between two branches in the same repository. If you’re working on a feature with someone and you both have write access to the project, you can push a topic branch to the repository and open a Pull Request on it to the `master` branch of that same project to initiate the code review and discussion process. No forking necessary.
- **Note:** There are actually quite a number of web services that make use of emoji characters these days. A great cheat sheet to reference to find emoji that expresses what you want to say can be found at:

## Related skills

- `git-github-maintaining-a-project` - Maintaining a Project
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-scripting-github` - Scripting GitHub

## Source

"Pro Git", pages 177-197. Sections: Contributing to a Project; Contributing to a Project > Forking Projects; Contributing to a Project > The GitHub Flow; Contributing to a Project > Advanced Pull Requests; Contributing to a Project > GitHub Flavored Markdown; Contributing to a Project > Keep your GitHub public repository up-to-date.
