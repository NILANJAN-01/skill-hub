# Getting Started

_Source: Pro Git, pages 16-31_

## Topics covered

- About Version Control
- A Short History of Git
- What is Git?
- The Command Line
- Installing Git
- First-Time Git Setup
- Getting Help
- Summary

**Key terms:** install, file, sudo, git, installer, dnf, config, files, gitconfig, distribution

## Key points

- Git Generally Only Adds Data When you do actions in Git, nearly all of them only add data to the Git database.
- Installing Git Before you start using Git, you have to make it available on your computer.
- After this is done, you can also get Git via Git itself for updates: `git clone https://git.kernel.org/pub/scm/git/git.git`.
- Now that you have Git on your system, you’ll want to do a few things to customize your Git environment.
- Git comes with a tool called git config that lets you get and set configuration variables that control all aspects of how Git looks and operates.
- You can make Git read and write to this file specifically by passing the --global option, and this affects all of the repositories you work with on your system. 3. config file in the Git directory (that is, .git/config) of whatever repository you’re currently using: Specific to that single repository.
- If you are using version 2.x or later of Git for Windows, there is also a system-level config file at C:\Documents and Settings\All Users\Application Data\Git\config on Windows XP, and in C:\ProgramData\Git\config on Windows Vista and newer.
- If you are using another editor, or a 32-bit version, please find specific instructions for how to set up your favorite editor with Git in git config core.editor commands.  You may find, if you don’t setup your editor like this, you get into a really confusing state when Git attempts to launch it.
- If you want to check your configuration settings, you can use the git config --list command to list all the settings Git can find at that point: `git config --list`.
- You can also check what Git thinks a specific key’s value is by typing git config <key>: `git config user.name`.
- If you ever need help while using Git, there are three equivalent ways to get the comprehensive manual page (manpage) help for any of the Git commands: `git help <verb>`.
- For example, you can get the manpage help for the git config command by running this: `git help config`.

## Commands / code

```
$ sudo dnf install git-all
$ sudo apt install git-all
$ git --version
$ sudo dnf install dh-autoreconf curl-devel expat-devel gettext-devel \
$ sudo apt-get install dh-autoreconf libcurl4-gnutls-dev libexpat1-dev \
$ sudo dnf install asciidoc xmlto docbook2X
$ sudo apt-get install asciidoc xmlto docbook2x
$ sudo apt-get install install-info
$ sudo dnf install getopt
$ sudo ln -s /usr/bin/db2x_docbook2texi /usr/bin/docbook2x-texi
$ tar -zxf git-2.8.0.tar.gz
$ cd git-2.8.0
$ make configure
$ ./configure --prefix=/usr
$ make all doc info
$ sudo make install install-doc install-html install-info
$ git clone https://git.kernel.org/pub/scm/git/git.git
$ git config --list --show-origin
$ git config --global user.name "John Doe"
$ git config --global user.email johndoe@example.com
$ git config --global core.editor emacs
$ git config --global core.editor "'C:/Program Files/Notepad++/notepad++.exe'
$ git config --global init.defaultBranch main
$ git config --list
$ git config user.name
$ git config --show-origin rerere.autoUpdate
$ git help <verb>
$ git <verb> --help
$ man git-<verb>
$ git help config
$ git add -h
```

## Rules, tips and warnings

- About Version Control What is “version control”, and why should you care?
- Version control is a system that records changes to a file or set of files over time so that you can recall specific versions later.
- Using a VCS also generally means that if you screw things up or lose files, you can easily recover.
- Distributed version control diagram Furthermore, many of these systems deal pretty well with having several remote repositories they can work with, so you can collaborate with different groups of people in different ways simultaneously within the same project.
- This is an important section to absorb, because if you understand what Git is and the fundamentals of how it works, then using Git effectively will probably be much easier for you.
- As you learn Git, try to clear your mind of the things you may know about other VCSs, such as CVS, Subversion or Perforce — doing so will help you avoid subtle confusion when using the tool.
- Even though Git’s user interface is fairly similar to these other VCSs, Git stores and thinks about information in a very different way, and understanding these differences will help you avoid becoming confused while using it.
- Storing data as snapshots of the project over time This is an important distinction between Git and nearly all other VCSs.
- If you want to see the changes introduced between the current version of a file and the file a month ago, Git can look up the file a month ago and do a local difference calculation, instead of having to either ask a remote server to do it or pull an older version of the file from the remote server to do it locally.
- This also means that there is very little you can’t do if you’re offline or off VPN.
- If you get on an airplane or a train and want to do a little work, you can commit happily (to your local copy, remember?) until you get to a network connection to upload.
- If you go home and can’t get your VPN client working properly, you can still work.
