---
name: git-installing-git
description: "Install or upgrade git on Linux, macOS or Windows. Use when you need to install git or for git: command not found."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Installing Git"
  category: git-getting-started
  source: "Pro Git, 2nd edition"
  pages: "24-27"
---

# Installing Git

You can either install it as a package or via another installer, or download the source code and compile it yourself.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `dnf install`: `sudo dnf install getopt`
- `apt-get install`: `sudo apt-get install install-info`
- `apt install`: `sudo apt install git-all`
- `git --version`
- `ln -s`: `sudo ln -s /usr/bin/db2x_docbook2texi /usr/bin/docbook2x-texi`
- `tar -zxf`: `tar -zxf git-2.8.0.tar.gz`
- `make configure`
- `./configure --prefix`: `./configure --prefix=/usr`
- `make all`: `make all doc info`
- `make install`: `sudo make install install-doc install-html install-info`
- `git clone`: `git clone https://git.kernel.org/pub/scm/git/git.git`

## Troubleshooting

- **Note:** This book was written using Git version 2. Since Git is quite excellent at preserving backwards compatibility, any recent version should work just fine. Though most of the commands we use should work even in ancient versions of Git, some of them might not or might act slightly differently.
- **Note:** Users of RHEL and RHEL-derivatives like CentOS and Scientific Linux will have to enable the EPEL repository to download the `docbook2X` package.

## Related skills

- `git-gitweb` - GitWeb
- `git-in-powershell` - Git in PowerShell
- `git-as-a-client` - Git as a Client
- `git-jgit` - JGit

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 24-27, CC BY-NC-SA 3.0._
