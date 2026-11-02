---
name: git-installing-git
description: "Installing Git playbook extracted from \"Pro Git\". You can either install it as a package or via another installer, or download the source code and compile it yourself. Use when the user asks about installing git, install git, git chocolatey package, git website, debian-based distribution, fedora, download; or mentions dnf install, apt-get install, apt install, make install, git --version, ln -s."
---

# Installing Git

You can either install it as a package or via another installer, or download the source code and compile it yourself.

_Built from "Pro Git" (pages 24-27) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **installing git** (install git, git chocolatey package, git website, debian-based distribution, fedora).
- The user wants to run or understand `dnf install`.
- The user wants to run or understand `apt-get install`.
- The user wants to run or understand `apt install`.
- The user wants to run or understand `make install`.
- If you want to install the basic Git tools on Linux via a binary installer, you can generally do so through the package management tool that comes with your distribution.
- To get an automated installation you can use the Git Chocolatey package.

## When NOT to use

- For gitweb, use the `git-gitweb` skill instead.
- For git in powershell, use the `git-in-powershell` skill instead.
- For git as a client, use the `git-as-a-client` skill instead.

## Key concepts

- If you want to install the basic Git tools on Linux via a binary installer, you can generally do so through the package management tool that comes with your distribution.
- There are several ways to install Git on macOS.
- If you want a more up to date version, you can also install it via a binary installer.
- A macOS Git installer is maintained and available for download at the Git website, at https://git-scm.com/ download/mac.
- There are also a few ways to install Git on Windows.
- To get an automated installation you can use the Git Chocolatey package.
- Some people may instead find it useful to install Git from source, because you’ll get the most recent version.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Installing on Linux

**Goal:** If you want to install the basic Git tools on Linux via a binary installer, you can generally do so through the package management tool that comes with your distribution.

**Steps:**

1. If you’re on Fedora (or any closely-related RPM-based distribution, such as RHEL or CentOS), you can use `dnf`:
   ```bash
   sudo dnf install git-all
   ```
2. If you’re on a Debian-based distribution, such as Ubuntu, try `apt`:
   ```bash
   sudo apt install git-all
   ```

### Installing on macOS

**Goal:** There are several ways to install Git on macOS.

**Steps:**

1. On Mavericks (10.9) or above you can do this simply by trying to run `git` from the Terminal the very first time.
   ```bash
   git --version
   ```

### Installing from Source

**Goal:** Some people may instead find it useful to install Git from source, because you’ll get the most recent version.

**Steps:**

1. For example, if you’re on a system that has `dnf` (such as Fedora) or `apt-get` (such as a Debian-based system), you can use one of these commands to install the minimal dependencies for compiling and installing the Git binaries:
   ```bash
   sudo dnf install dh-autoreconf curl-devel expat-devel gettext-devel \
   openssl-devel perl-devel zlib-devel
   sudo apt-get install dh-autoreconf libcurl4-gnutls-dev libexpat1-dev \
   gettext libz-dev libssl-dev
   ```
2. In order to be able to add the documentation in various formats (doc, html, info), these additional dependencies are required:
   ```bash
   sudo dnf install asciidoc xmlto docbook2X
   sudo apt-get install asciidoc xmlto docbook2x
   ```
3. If you’re using a Debian-based distribution (Debian/Ubuntu/Ubuntu-derivatives), you also need the `install-info` package:
   ```bash
   sudo apt-get install install-info
   ```
4. If you’re using a RPM-based distribution (Fedora/RHEL/RHEL-derivatives), you also need the `getopt` package (which is already installed on a Debian-based distro):
   ```bash
   sudo dnf install getopt
   ```
5. Additionally, if you’re using Fedora/RHEL/RHEL-derivatives, you need to do this:
   ```bash
   sudo ln -s /usr/bin/db2x_docbook2texi /usr/bin/docbook2x-texi
   ```
6. Then, compile and install:
   ```bash
   tar -zxf git-2.8.0.tar.gz
   cd git-2.8.0
   make configure
   ./configure --prefix=/usr
   make all doc info
   sudo make install install-doc install-html install-info
   ```

_1 more step(s) in references/procedures.md._

More procedures in [references/procedures.md](references/procedures.md):

- Installing from Source

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `dnf install` | If you’re on Fedora (or any closely-related RPM-based distribution, such as RHEL or CentOS), you can use `dnf` | `sudo dnf install getopt` |
| `apt-get install` | For example, if you’re on a system that has `dnf` (such as Fedora) or `apt-get` (such as a Debian-based system), you can use one of these commands to install the minimal dependencies for compiling and installing the Git binaries | `sudo apt-get install install-info` |
| `apt install` | If you’re on a Debian-based distribution, such as Ubuntu, try `apt` | `sudo apt install git-all` |
| `git --version` | On Mavericks (10.9) or above you can do this simply by trying to run `git` from the Terminal the very first time. | `git --version` |
| `ln -s` | Additionally, if you’re using Fedora/RHEL/RHEL-derivatives, you need to do this | `sudo ln -s /usr/bin/db2x_docbook2texi /usr/bin/docbook2x-texi` |
| `tar -zxf` | Then, compile and install | `tar -zxf git-2.8.0.tar.gz` |
| `make configure` | Then, compile and install | `make configure` |
| `./configure --prefix` | Then, compile and install | `./configure --prefix=/usr` |
| `make all` | Then, compile and install | `make all doc info` |
| `make install` | Then, compile and install | `sudo make install install-doc install-html install-info` |
| `git clone` | After this is done, you can also get Git via Git itself for updates | `git clone https://git.kernel.org/pub/scm/git/git.git` |

## Troubleshooting

- **Note:** This book was written using Git version 2. Since Git is quite excellent at preserving backwards compatibility, any recent version should work just fine. Though most of the commands we use should work even in ancient versions of Git, some of them might not or might act slightly differently.
- **Note:** Users of RHEL and RHEL-derivatives like CentOS and Scientific Linux will have to enable the EPEL repository to download the `docbook2X` package.

## Related skills

- `git-gitweb` - GitWeb
- `git-in-powershell` - Git in PowerShell
- `git-as-a-client` - Git as a Client
- `git-jgit` - JGit

## Source

"Pro Git", pages 24-27. Sections: Installing Git; Installing Git > Installing on Linux; Installing Git > Installing on macOS; Installing Git > Installing on Windows; Installing Git > Installing from Source.
