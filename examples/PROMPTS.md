# Example prompts

<!-- Generated from examples/prompts.json by tools/build_catalog.py - do not edit by hand. -->

202 things you can say to your AI coding agent, for all 66 skills. Install a skill ([guide](../GUIDE.md)), then just ask: the agent loads the skill when your request matches its description. To force a skill, start with *"Use the &lt;skill-name&gt; skill: …"*.

**Categories:** [Hub tools](#hub-tools) · [Android: UI test automation](#android-ui-test-automation) · [Images: pixels & description](#images-pixels--description) · [Git: getting started](#git-getting-started) · [Git: branching & merging](#git-branching--merging) · [Git: remotes & collaboration](#git-remotes--collaboration) · [Git: power tools](#git-power-tools) · [Git: customization & hooks](#git-customization--hooks) · [Git: internals](#git-internals) · [Git: other systems & APIs](#git-other-systems--apis) · [Git: full reference](#git-full-reference)

## Hub tools

Install the whole category: `--plugin hub-tools`

### Contribute a skill to the hub

[`contribute-skill`](../skills/contribute-skill/SKILL.md) · install: `--skill contribute-skill`

- “Add a new skill called docker-compose-basics to skill-hub.”
- “validate_skills.py says my skill is 'not listed in any plugin'. How do I fix it?”
- “Create a new plugin category in skill-hub for Kubernetes skills.”

### Find & install hub skills

[`find-skills`](../skills/find-skills/SKILL.md) · install: `--skill find-skills`

- “Is there a skill in skill-hub for git submodules? Which plugin has it?”
- “What skills does skill-hub offer for working with Git remotes?”
- “Find me a skill that helps with resolving merge conflicts and install it for this project.”

### Skillforge: PDF to skills

[`skillforge`](../skills/skillforge/SKILL.md) · install: `--skill skillforge`

- “Turn this Kubernetes handbook PDF into Agent Skills.”
- “Generate skills only for 'backup, restore, replication' from postgres-manual.pdf.”
- “Show me the plan of skills skillforge would create from book.pdf before writing anything.”

## Android: UI test automation

Install the whole category: `--plugin android-automation`

### Android UIAutomator dump to locators

[`android-uiautomator-locators`](../skills/android-uiautomator-locators/SKILL.md) · install: `--skill android-uiautomator-locators`

- “Here's window_dump.xml from our head unit. Generate a JSON with keyword names and resource ids for our tests.”
- “Convert all the window_dump.xml files in dumps/ into locator JSON files in tests/locators.”
- “Dump the current screen from the connected device and generate the locator JSON.”
- “This Compose screen has no resource-ids. Give me the best locators you can from this uiautomator dump.”

## Images: pixels & description

Install the whole category: `--plugin image-tools`

### Image inspector: pixels and description

[`image-inspector`](../skills/image-inspector/SKILL.md) · install: `--skill image-inspector`

- “Describe this screenshot.png for me: size, main colours and what's on it.”
- “What is the exact hex colour of the pixel at 120,48 in banner.jpg?”
- “Give me the dominant colour palette of logo.png and tell me if it has a transparent background.”
- “Export every pixel of icon.png to a CSV and read the text in scan.jpg.”
- “Where is play_icon.png on this screenshot? Give me the tap coordinates.”
- “Compare after.png with before.png and show me what changed, ignoring the clock.”

## Git: getting started

Install the whole category: `--plugin git-getting-started`

### Basic Snapshotting

[`git-basic-snapshotting`](../skills/git-basic-snapshotting/SKILL.md) · install: `--skill git-basic-snapshotting`

- “Explain the basic add, status, diff and commit workflow in Git.”
- “How do I remove a file from Git but keep it on disk?”
- “Rename a file so Git tracks the move.”

### First-Time Git Setup

[`git-first-time-git-setup`](../skills/git-first-time-git-setup/SKILL.md) · install: `--skill git-first-time-git-setup`

- “I just installed Git. What should I configure first?”
- “Set my Git name and email globally.”
- “Make VS Code my default Git editor and set the default branch name to main.”

### Getting a Git Repository

[`git-getting-a-git-repository`](../skills/git-getting-a-git-repository/SKILL.md) · install: `--skill git-getting-a-git-repository`

- “Turn this existing folder into a Git repository.”
- “Clone https://github.com/libgit2/libgit2 into a folder named mylibgit.”
- “What's the difference between git init and git clone?”

### Getting Help

[`git-getting-help`](../skills/git-getting-help/SKILL.md) · install: `--skill git-getting-help`

- “How do I see the manual page for git commit?”
- “Show me a quick summary of the options for git add.”
- “Where can I get help with Git commands offline?”

### Git Aliases

[`git-aliases`](../skills/git-aliases/SKILL.md) · install: `--skill git-aliases`

- “Create a git alias so 'git st' runs git status.”
- “Make a 'git last' command that shows the last commit.”
- “How do I create a git alias that runs an external shell command?”

### Installing Git

[`git-installing-git`](../skills/git-installing-git/SKILL.md) · install: `--skill git-installing-git`

- “How do I install Git on Ubuntu?”
- “Install the latest Git on my Mac.”
- “I want to build Git from source. What do I need?”

### Recording Changes to the Repository

[`git-recording-changes-to-the-repository`](../skills/git-recording-changes-to-the-repository/SKILL.md) · install: `--skill git-recording-changes-to-the-repository`

- “How do I stage only some files and commit them?”
- “Make Git ignore all .log files and the build/ folder.”
- “Show me what I've staged versus what I've changed but not staged.”

### Setup and Config

[`git-setup-and-config`](../skills/git-setup-and-config/SKILL.md) · install: `--skill git-setup-and-config`

- “Show me all my Git config settings and where each one comes from.”
- “What's the difference between --system, --global and --local config in Git?”
- “How do I change the editor Git opens for commit messages?”

### Tagging

[`git-tagging`](../skills/git-tagging/SKILL.md) · install: `--skill git-tagging`

- “Create an annotated tag v1.2.0 with a message and push it.”
- “List all tags that start with v2.”
- “Delete a tag both locally and on the remote.”

### Undoing Things

[`git-undoing-things`](../skills/git-undoing-things/SKILL.md) · install: `--skill git-undoing-things`

- “I forgot to add a file to my last commit. How do I fix it?”
- “Unstage a file I accidentally added.”
- “Throw away my local changes to config.yml.”

### Viewing the Commit History

[`git-viewing-the-commit-history`](../skills/git-viewing-the-commit-history/SKILL.md) · install: `--skill git-viewing-the-commit-history`

- “Show the last 5 commits with the diffs.”
- “Find the commits that added or removed the string 'getUserToken'.”
- “Show a one-line graph of the history of all branches.”

## Git: branching & merging

Install the whole category: `--plugin git-branching`

### Advanced Merging

[`git-advanced-merging`](../skills/git-advanced-merging/SKILL.md) · install: `--skill git-advanced-merging`

- “Abort this merge, it went wrong.”
- “During a merge conflict, take their version of every conflicting file.”
- “Undo a merge commit that was already pushed.”

### Basic Branching and Merging

[`git-basic-branching-and-merging`](../skills/git-basic-branching-and-merging/SKILL.md) · install: `--skill git-basic-branching-and-merging`

- “Create a hotfix branch, fix the bug, and merge it back into main.”
- “I got 'CONFLICT (content): Merge conflict in index.html'. What do I do?”
- “What's the difference between a fast-forward merge and a merge commit?”

### Branch Management

[`git-branch-management`](../skills/git-branch-management/SKILL.md) · install: `--skill git-branch-management`

- “List the branches already merged into main so I can delete them.”
- “Rename my local branch from 'feat' to 'feature/login'.”
- “Show each branch with its last commit.”

### Branches in a Nutshell

[`git-branches-in-a-nutshell`](../skills/git-branches-in-a-nutshell/SKILL.md) · install: `--skill git-branches-in-a-nutshell`

- “Explain how Git branches and HEAD actually work.”
- “Create a branch called testing and switch to it.”
- “Show which commit each branch points to.”

### Rebasing

[`git-rebasing`](../skills/git-rebasing/SKILL.md) · install: `--skill git-rebasing`

- “Rebase my feature branch onto the latest main without a merge commit.”
- “Move a branch that was based on 'server' so it sits directly on main using --onto.”
- “When should I avoid rebasing? I already pushed my branch.”

### Remote Branches

[`git-remote-branches`](../skills/git-remote-branches/SKILL.md) · install: `--skill git-remote-branches`

- “Make my local branch track origin/develop.”
- “Delete the branch 'old-feature' on the remote.”
- “Show how far ahead of or behind its upstream each of my branches is.”

### Rerere

[`git-rerere`](../skills/git-rerere/SKILL.md) · install: `--skill git-rerere`

- “Make Git remember how I resolved conflicts so it reapplies the fix next time.”
- “Turn on rerere and show me what it has recorded.”
- “I keep resolving the same conflict on every rebase. How can Git automate that?”

## Git: remotes & collaboration

Install the whole category: `--plugin git-collaboration`

### Contributing to a Project

[`git-distributed-git-contributing-to-a-project`](../skills/git-distributed-git-contributing-to-a-project/SKILL.md) · install: `--skill git-distributed-git-contributing-to-a-project`

- “What makes a good commit message?”
- “How do I contribute to a project by sending patches by email?”
- “Squash my topic branch into one commit before sending it upstream.”

### Contributing to a Project

[`git-github-contributing-to-a-project`](../skills/git-github-contributing-to-a-project/SKILL.md) · install: `--skill git-github-contributing-to-a-project`

- “Fork a GitHub project, make a change, and open a pull request.”
- “Update my pull request after the maintainer asked for changes.”
- “Sync my fork with the upstream repository.”

### Credential Storage

[`git-credential-storage`](../skills/git-credential-storage/SKILL.md) · install: `--skill git-credential-storage`

- “Stop Git asking for my password on every push.”
- “Cache my Git credentials for 1 hour.”
- “Which credential helper should I use on Windows or macOS?”

### Generating Your SSH Public Key

[`git-generating-your-ssh-public-key`](../skills/git-generating-your-ssh-public-key/SKILL.md) · install: `--skill git-generating-your-ssh-public-key`

- “Generate an SSH key to use with Git.”
- “Do I already have an SSH key? Where is it stored?”
- “How do I give my SSH public key to the Git server admin?”

### Getting Git on a Server

[`git-getting-git-on-a-server`](../skills/git-getting-git-on-a-server/SKILL.md) · install: `--skill git-getting-git-on-a-server`

- “Create a bare repository to put on my server.”
- “Set up a shared Git repo on a Linux server that my team can push to.”
- “Make a server repository group-writable for all developers.”

### Git Daemon

[`git-daemon`](../skills/git-daemon/SKILL.md) · install: `--skill git-daemon`

- “Serve my repositories read-only with git daemon.”
- “Run git daemon as a systemd service.”
- “Allow anonymous cloning of a repository over git://.”

### GitWeb

[`git-gitweb`](../skills/git-gitweb/SKILL.md) · install: `--skill git-gitweb`

- “Set up GitWeb to browse my repositories in a web browser.”
- “Run a quick GitWeb instance with git instaweb.”
- “Install GitWeb on Apache for all repos in /srv/git.”

### Maintaining a Project

[`git-distributed-git-maintaining-a-project`](../skills/git-distributed-git-maintaining-a-project/SKILL.md) · install: `--skill git-distributed-git-maintaining-a-project`

- “Apply a patch someone emailed me with git am.”
- “Review the changes a contributor's branch introduces before I merge it.”
- “Create a release tarball and a shortlog for my project's release notes.”

### Maintaining a Project

[`git-github-maintaining-a-project`](../skills/git-github-maintaining-a-project/SKILL.md) · install: `--skill git-github-maintaining-a-project`

- “Check out a GitHub pull request locally to test it.”
- “Add collaborators to my GitHub repository.”
- “How do I use pull request refs to fetch all open PRs?”

### Scripting GitHub

[`git-scripting-github`](../skills/git-scripting-github/SKILL.md) · install: `--skill git-scripting-github`

- “Use the GitHub API to comment on an issue.”
- “Set the commit status on GitHub from a script.”
- “Get notified with a webhook when someone pushes to my repo.”

### Setting Up the Server

[`git-setting-up-the-server`](../skills/git-setting-up-the-server/SKILL.md) · install: `--skill git-setting-up-the-server`

- “Set up a git user on my server that accepts SSH keys from my team.”
- “Restrict the git user so it can only run Git commands (git-shell).”
- “Add a new developer's public key to my Git server.”

### Smart HTTP

[`git-smart-http`](../skills/git-smart-http/SKILL.md) · install: `--skill git-smart-http`

- “Set up Smart HTTP for Git with Apache.”
- “Configure git-http-backend so pushes over HTTP require a password.”
- “Host Git over HTTPS on my own server.”

### The Protocols

[`git-the-protocols`](../skills/git-the-protocols/SKILL.md) · install: `--skill git-the-protocols`

- “Should I use SSH or HTTPS to host my Git repository?”
- “Explain the local, HTTP, SSH and git:// protocols and their pros and cons.”
- “Clone a repository from a shared network folder.”

### Working with Remotes

[`git-working-with-remotes`](../skills/git-working-with-remotes/SKILL.md) · install: `--skill git-working-with-remotes`

- “List the remotes of this repository with their URLs.”
- “Add a second remote called upstream and fetch from it.”
- “Rename the remote 'origin' to 'github'.”

## Git: power tools

Install the whole category: `--plugin git-power-tools`

### Bundling

[`git-bundling`](../skills/git-bundling/SKILL.md) · install: `--skill git-bundling`

- “Send my repository to someone without network access.”
- “Create a git bundle with only the last 10 commits.”
- “Clone from a .bundle file.”

### Debugging with Git

[`git-debugging-with-git`](../skills/git-debugging-with-git/SKILL.md) · install: `--skill git-debugging-with-git`

- “Use git bisect to find which commit introduced a bug.”
- “Who last changed lines 10 to 20 of app.py?”
- “Automate git bisect with a test script.”

### Interactive Staging

[`git-interactive-staging`](../skills/git-interactive-staging/SKILL.md) · install: `--skill git-interactive-staging`

- “Stage only some of the changes in a file.”
- “Use git add -p to split my changes into two commits.”
- “Walk me through git add -i.”

### Replace

[`git-replace`](../skills/git-replace/SKILL.md) · install: `--skill git-replace`

- “Make Git treat one commit as if it were another with git replace.”
- “Graft old project history onto a shortened repository.”
- “How do I list and delete git replace refs?”

### Reset Demystified

[`git-reset-demystified`](../skills/git-reset-demystified/SKILL.md) · install: `--skill git-reset-demystified`

- “Explain the difference between git reset --soft, --mixed and --hard.”
- “Undo my last commit but keep the changes staged.”
- “What's the difference between git reset and git checkout on a file?”

### Revision Selection

[`git-revision-selection`](../skills/git-revision-selection/SKILL.md) · install: `--skill git-revision-selection`

- “What does HEAD~3 versus HEAD^2 mean?”
- “Show the commits on my branch that are not on main.”
- “Use the reflog to find where my branch pointed yesterday.”

### Rewriting History

[`git-rewriting-history`](../skills/git-rewriting-history/SKILL.md) · install: `--skill git-rewriting-history`

- “Change the message of a commit three commits back.”
- “Squash my last 4 commits into one.”
- “Remove a file with a leaked password from the entire Git history.”

### Searching

[`git-searching`](../skills/git-searching/SKILL.md) · install: `--skill git-searching`

- “Search the whole repository for 'TODO' with line numbers.”
- “Find when the function parseConfig was introduced.”
- “Show the history of a single function in a file.”

### Signing Your Work

[`git-signing-your-work`](../skills/git-signing-your-work/SKILL.md) · install: `--skill git-signing-your-work`

- “Sign my commits with GPG.”
- “Create a signed tag and verify it.”
- “Make Git sign every commit automatically.”

### Stashing and Cleaning

[`git-stashing-and-cleaning`](../skills/git-stashing-and-cleaning/SKILL.md) · install: `--skill git-stashing-and-cleaning`

- “I have half-done changes and need to switch branches urgently.”
- “Stash my changes including untracked files, then restore them later.”
- “Remove all untracked files and folders, but show me what will be deleted first.”

### Submodules

[`git-submodules`](../skills/git-submodules/SKILL.md) · install: `--skill git-submodules`

- “Add a library as a git submodule.”
- “Clone a repository together with all its submodules.”
- “Update all submodules to their latest upstream commits.”

## Git: customization & hooks

Install the whole category: `--plugin git-customization`

### An Example Git-Enforced Policy

[`git-an-example-git-enforced-policy`](../skills/git-an-example-git-enforced-policy/SKILL.md) · install: `--skill git-an-example-git-enforced-policy`

- “Enforce a commit message format on the server with an update hook.”
- “Restrict which users can push to which directories.”
- “Prevent non-fast-forward pushes on the server.”

### Environment Variables

[`git-environment-variables`](../skills/git-environment-variables/SKILL.md) · install: `--skill git-environment-variables`

- “Which environment variable sets the committer date in Git?”
- “Debug a slow git fetch with GIT_TRACE.”
- “Use a different SSH command for one Git operation.”

### Git Attributes

[`git-attributes`](../skills/git-attributes/SKILL.md) · install: `--skill git-attributes`

- “Tell Git to treat *.pdf files as binary.”
- “Diff Word documents in Git in a readable way.”
- “Keep a config file's local version during merges with a merge strategy attribute.”

### Git Configuration

[`git-configuration`](../skills/git-configuration/SKILL.md) · install: `--skill git-configuration`

- “Make Git colorize output and use a custom pager.”
- “Configure core.autocrlf correctly for a team on Windows and Linux.”
- “Set up a global .gitignore and a commit message template.”

### Git Hooks

[`git-hooks`](../skills/git-hooks/SKILL.md) · install: `--skill git-hooks`

- “Block commits whose message doesn't start with a ticket ID like ABC-123.”
- “Run my test suite before every commit with a pre-commit hook.”
- “Which server-side hooks can reject a push?”

## Git: internals

Install the whole category: `--plugin git-internals`

### Git Objects

[`git-objects`](../skills/git-objects/SKILL.md) · install: `--skill git-objects`

- “Explain blobs, trees and commits in Git internals.”
- “Create a Git object by hand with hash-object and read it back with cat-file.”
- “Show the tree object of the latest commit.”

### Git References

[`git-references`](../skills/git-references/SKILL.md) · install: `--skill git-references`

- “How are branches stored inside .git?”
- “Update a branch ref directly with git update-ref.”
- “What is HEAD internally, and what's a symbolic ref?”

### Maintenance and Data Recovery

[`git-maintenance-and-data-recovery`](../skills/git-maintenance-and-data-recovery/SKILL.md) · install: `--skill git-maintenance-and-data-recovery`

- “I deleted a branch by accident. How do I get it back?”
- “Find and remove a huge file that is bloating my repository.”
- “Recover lost commits with git fsck and the reflog.”

### Packfiles

[`git-packfiles`](../skills/git-packfiles/SKILL.md) · install: `--skill git-packfiles`

- “Why is my .git folder so big? Explain packfiles.”
- “Inspect the contents of a packfile with git verify-pack.”
- “Run git gc and explain what it does.”

### Plumbing and Porcelain

[`git-plumbing-and-porcelain`](../skills/git-plumbing-and-porcelain/SKILL.md) · install: `--skill git-plumbing-and-porcelain`

- “What's the difference between plumbing and porcelain commands in Git?”
- “What's inside the .git directory?”
- “Which Git commands are safe to use in scripts?”

### The Refspec

[`git-the-refspec`](../skills/git-the-refspec/SKILL.md) · install: `--skill git-the-refspec`

- “Explain the refspec +refs/heads/*:refs/remotes/origin/*.”
- “Fetch only the main branch from a remote by default.”
- “Push my local branch to a differently named remote branch.”

### Transfer Protocols

[`git-transfer-protocols`](../skills/git-transfer-protocols/SKILL.md) · install: `--skill git-transfer-protocols`

- “How does git fetch talk to the server over HTTP?”
- “Explain the dumb versus smart Git transfer protocols.”
- “What happens during git push over SSH (send-pack and receive-pack)?”

## Git: other systems & APIs

Install the whole category: `--plugin git-integrations`

### Git as a Client

[`git-as-a-client`](../skills/git-as-a-client/SKILL.md) · install: `--skill git-as-a-client`

- “Use Git with a Subversion repository via git svn.”
- “Push my Git commits back to SVN with git svn dcommit.”
- “Work with a Mercurial or Perforce server from Git.”

### Git in PowerShell

[`git-in-powershell`](../skills/git-in-powershell/SKILL.md) · install: `--skill git-in-powershell`

- “Set up posh-git so PowerShell shows Git status in my prompt.”
- “Install posh-git on Windows.”
- “Get Git tab completion in PowerShell.”

### JGit

[`git-jgit`](../skills/git-jgit/SKILL.md) · install: `--skill git-jgit`

- “Use JGit to open a repository and read the latest commit in Java.”
- “Clone a repository from Java code.”
- “How do I add JGit to my Maven project?”

### Libgit2

[`git-libgit2`](../skills/git-libgit2/SKILL.md) · install: `--skill git-libgit2`

- “Use libgit2 to read a commit in C.”
- “What language bindings exist for libgit2?”
- “Create a commit programmatically with libgit2.”

### Migrating to Git

[`git-migrating-to-git`](../skills/git-migrating-to-git/SKILL.md) · install: `--skill git-migrating-to-git`

- “Migrate our SVN repository to Git, keeping history and authors.”
- “Convert a Mercurial repo to Git.”
- “Write a custom importer with git fast-import.”

## Git: full reference

Install the whole category: `--plugin git-reference`

### Pro Git (full reference)

[`git-pro`](../skills/git-pro/SKILL.md) · install: `--skill git-pro`

- “Explain how Git stores data compared to other version control systems.”
- “Give me an overview of Git's distributed workflows.”
- “What does the Pro Git book say about customizing Git?”
