---
name: git-pro
description: "Index of the Pro Git book, one reference per chapter. Use when a git question spans topics or no other git skill fits."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Pro Git (full reference)"
  category: git-reference
  source: "Pro Git, 2nd edition"
  pages: "1-501"
---

# Pro Git

This skill contains knowledge extracted from **Pro Git** (501 pages).

## How to use this skill

1. Find the relevant section in the index below (match the user's question against the topics).
2. Read only that `references/` file - each one holds key points, commands and tips for one section.
3. Answer using that material; cite the section and page range when helpful.

## Section index

| Section | Pages | Topics |
|---|---|---|
| [Introduction](references/introduction.md) | 14-15 | vcss, svn, enforce, life, appendix, technical |
| [Getting Started](references/getting-started.md) | 16-31 | About Version Control, A Short History of Git, What is Git?, The Command Line, Installing Git, First-Time Git Setup |
| [Git Basics](references/git-basics.md) | 32-68 | Getting a Git Repository, Recording Changes to the Repository, Viewing the Commit History, Undoing Things, Working with Remotes, Tagging |
| [Git Branching](references/git-branching.md) | 69-110 | Branches in a Nutshell, Basic Branching and Merging, Branch Management, Branching Workflows, Remote Branches, Rebasing |
| [Git on the Server](references/git-on-the-server.md) | 111-131 | The Protocols, Getting Git on a Server, Generating Your SSH Public Key, Setting Up the Server, Git Daemon, Smart HTTP |
| [Distributed Git](references/distributed-git.md) | 132-171 | Distributed Workflows, Contributing to a Project, Maintaining a Project, Summary |
| [GitHub](references/github.md) | 172-223 | Account Setup and Configuration, Contributing to a Project, Maintaining a Project, Managing an organization, Scripting GitHub, Summary |
| [Git Tools](references/git-tools.md) | 224-341 | Revision Selection, Interactive Staging, Stashing and Cleaning, Signing Your Work, Searching, Rewriting History |
| [Customizing Git](references/customizing-git.md) | 342-372 | Git Configuration, Git Attributes, Git Hooks, An Example Git-Enforced Policy, Summary |
| [Git and Other Systems](references/git-and-other-systems.md) | 373-419 | Git as a Client, Migrating to Git, Summary |
| [Git Internals](references/git-internals.md) | 420-458 | Plumbing and Porcelain, Git Objects, Git References, Packfiles, The Refspec, Transfer Protocols |
| [Appendix A: Git in Other Environments](references/appendix-a-git-in-other-environments.md) | 459-471 | Graphical Interfaces, Git in Visual Studio, Git in Visual Studio Code, Git in IntelliJ / PyCharm / WebStorm / PhpStorm / RubyMine, Git in Sublime Text, Git in Bash |
| [Appendix B: Embedding Git in your Applications](references/appendix-b-embedding-git-in-your-applications.md) | 472-483 | Command-line Git, Libgit2, JGit, go-git, Dulwich |
| [Appendix C: Git Commands](references/appendix-c-git-commands.md) | 484-498 | Setup and Config, Getting and Creating Projects, Basic Snapshotting, Branching and Merging, Sharing and Updating Projects, Inspection and Comparison |

## Quick reference: most-used commands

_Ranked by how often they appear in the document; one example each._

```
$ git log
$ git config --list
$ git commit --amend
$ git checkout -b iss53
$ git push origin --all
$ git clone hg::/tmp/hello /tmp/hello-git
$ git merge hotfix
$ git branch -v
$ git show v1.4
$ git cat-file -p HEAD
$ git add -h
$ git remote
$ git diff
$ git fetch pb
$ git submodule update --init
$ git tag
$ git stash
$ git svn clone file:///tmp/test-svn -s
$ git init
$ git rebase master
$ git rm PROJECTS.md
$ git bisect start
$ git --version
$ git status
$ git reset --hard HEAD^
$ git clean -f
$ git p4 submit -n
$ git am --resolved
$ git bundle verify ../commits-bad.bundle
$ hg log -G
$ ssh user@git.example.com
$ git apply --whitespace=fix <patch>
$ git pull https://github.com/onetimeguy/project
$ gpg --gen-key
$ git archive @ | tar xfO - LAST_COMMIT
$ git filter-branch --commit-filter '
$ git reflog
$ git grep -n gmtime_r
$ tree
$ git rerere status
```

## Key rules and tips

- This includes setting up hook scripts to enforce or encourage customized policies and using environment configuration settings so you can work the way you want to.
- Now that you know all about Git and can wield it with power and grace, you can move on to discuss how Git stores its objects, what the object model is, details of packfiles, server protocols, and more.
- About Version Control What is “version control”, and why should you care?
- Version control is a system that records changes to a file or set of files over time so that you can recall specific versions later.
- Git Basics If you can read only one chapter to get going with Git, this is it.
- You can take a local directory that is currently not under version control, and turn it into a Git repository, or 2.
- Note that this is a lot different than the concept of HEAD in other VCSs you may be used to, such as Subversion or CVS.
- HEAD pointing to a branch You can easily see this by running a simple git log command that shows you where the branch pointers are pointing.
- Git on the Server At this point, you should be able to do most of the day-to-day tasks for which you’ll be using Git.
- Although you can technically push changes to and pull changes from individuals' repositories, doing so is discouraged because you can fairly easily confuse what they’re working on if you’re not careful.
- The second developer must merge in the first one’s work before pushing changes up, so as not to overwrite the first developer’s changes.
- If you are already comfortable with a centralized workflow in your company or team, you can easily continue using that workflow with Git.
- The “SSH keys” link From there, click the “Add an SSH key” button, give your key a name, paste the contents of your ~/.ssh/id_rsa.pub (or whatever you named it) public-key file into the text area, and click “Add key”.  Be sure to name your SSH key something you can remember.
- "My Laptop" or "Work Account") so that if you need to revoke a key later, you can easily tell which one you’re looking for.
- Single Revisions You can obviously refer to any single commit by its full, 40-character SHA-1 hash, but there are more human-friendly ways to refer to commits as well.
- You can inspect that commit with any of the following variations of git show (assuming the shorter versions are unambiguous): `git show 1c002dd4b536e7479fe34593e72e6c6c1819e53b`.
- You can make Git read and write to this file by passing the --global option.
- Each of these “levels” (system, global, local) overwrites values in the previous level, so values in .git/config trump those in [path]/etc/gitconfig, for instance.  Git’s configuration files are plain-text, so you can also set these values by manually editing the file and inserting the correct syntax.
- Usually, you can’t immediately switch every project you come in contact with to Git.
- This tool allows you to use Git as a valid client to a Subversion server, so you can use all the local features of Git and then push to a Subversion server as if you were using Subversion locally.
