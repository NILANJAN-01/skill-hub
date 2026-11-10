# Appendix A: Git in Other Environments

_Source: Pro Git, pages 459-471_

## Topics covered

- Graphical Interfaces
- Git in Visual Studio
- Git in Visual Studio Code
- Git in IntelliJ / PyCharm / WebStorm / PhpStorm / RubyMine
- Git in Sublime Text
- Git in Bash
- Git in Zsh
- Git in PowerShell
- Summary

**Key terms:** posh-git, powershell, gitk, git-prompt, prompt, vcs_info, zsh, git-gui, remotesigned, bash

## Key points

- Appendix A: Git in Other Environments If you read through the whole book, you’ve learned a lot about how to use Git at the command line.
- Now we’ll take a look at some of the other kinds of environments where Git can be useful, and how other applications (including yours) work alongside Git.
- Think of it like a powerful GUI shell over git log and git grep.
- Just cd into a Git repository, and type: `gitk [git log options]`.
- Check your version by typing git version, then use git checkout tags/vX.Y.Z, where vX.Y.Z corresponds to the version of Git you are using.
- Git in Zsh Zsh also ships with a tab-completion library for Git.
- Instead of vcs_info, you might prefer the prompt customization script that ships with Git, called git-prompt.sh; see https://github.com/git/git/blob/master/contrib/completion/git-prompt.sh for details. git-prompt.sh is compatible with both Bash and Zsh.

## Commands / code

```
$ gitk [git log options]
$ git gui
$ git chec<tab>
$ git che<tab>
precmd_vcs_info() { vcs_info }
> Set-ExecutionPolicy -Scope LocalMachine -ExecutionPolicy RemoteSigned -Force
> Install-Module posh-git -Scope CurrentUser -Force
> Install-Module posh-git -Scope CurrentUser -AllowPrerelease -Force # Newer beta
> Install-Module PowerShellGet -Force -SkipPublisherCheck
> Import-Module posh-git
> Add-PoshGitToProfile -AllHosts
> Import-Module <path-to-uncompress-folder>\src\posh-git.psd1
```

## Rules, tips and warnings

- You can work with local files, connect your repository to others over a network, and work effectively with others.
- But the story doesn’t end there; Git is usually used as part of a larger ecosystem, and the terminal isn’t always the best way to work with it.
- It’s important to note that different interfaces are tailored for different workflows.
- Also note that there’s nothing these graphical clients can do that the command-line client can’t; the command-line is still where you’ll have the most power and control when working with your repositories. gitk and git-gui When you install Git, you also get its visual tools, gitk and git-gui. gitk is a graphical history viewer.
- You can move entire files between the two states by clicking on their icons, or you can select a file for viewing by clicking on its name.
- You can stage individual hunks (or individual lines) by right-clicking in this area.
- You can also choose to amend the last commit by choosing the “Amend” radio button, which will update the “Staged Changes” area with the contents of the last commit.
- Then you can simply stage or unstage some changes, alter the commit message, and click “Commit” again to replace the old commit with a new one. gitk and git-gui are examples of task-oriented tools.
- While they’re designed to highlight GitHub’s service and recommended workflow, they will happily work with any repository, and do network operations with any Git host.
- Recommended Workflow Once it’s installed and configured, you can use the GitHub client for many common Git tasks.
- However, if your workflow is different, or you want more control over how and when network operations are done, we recommend you use another client or the command line.
- Git in Bash If you’re a Bash user, you can tap into some of your shell’s features to make your experience with Git a lot friendlier.
