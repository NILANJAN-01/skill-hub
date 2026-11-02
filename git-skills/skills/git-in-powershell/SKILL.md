---
name: git-in-powershell
description: "Git in PowerShell playbook extracted from \"Pro Git\". Before you’re able to run PowerShell scripts on your machine, you need to set your local ExecutionPolicy to RemoteSigned (basically, anything except Undefined and Restricted). Use when the user asks about git in powershell, legacy command-line terminal, customized git experience, n’t really capable, posh-git, remotesigned, scope."
---

# Git in PowerShell

Before you’re able to run PowerShell scripts on your machine, you need to set your local `ExecutionPolicy` to `RemoteSigned` (basically, anything except `Undefined` and `Restricted`).

_Built from "Pro Git" (pages 469-471) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **git in powershell** (legacy command-line terminal, customized git experience, n’t really capable, posh-git, remotesigned).
- If you have at least PowerShell 5 or PowerShell 4 with PackageManagement installed, you can use the package manager to install posh-git for you.
- If you want to install posh-git for all users, use `-Scope AllUsers` instead and execute the command from an elevated PowerShell console.

## When NOT to use

- For installing git, use the `git-installing-git` skill instead.
- For scripting github, use the `git-scripting-github` skill instead.
- For git configuration, use the `git-configuration` skill instead.

## Key concepts

- More about PowerShell Scopes: https://learn.microsoft.com/en-us/powershell/module/ microsoft.powershell.core/about/about_scopes.
- More about PowerShell ExecutionPolicy: https://learn.microsoft.com/en-us/powershell/module/ microsoft.powershell.security/set-executionpolicy.
- If you have at least PowerShell 5 or PowerShell 4 with PackageManagement installed, you can use the package manager to install posh-git for you.
- More information about PowerShell Gallery: https://learn.microsoft.com/en-us/powershell/ scripting/gallery/overview.
- If you want to install posh-git for all users, use `-Scope AllUsers` instead and execute the command from an elevated PowerShell console.
- To have posh-git imported every time PowerShell starts, execute the `Add-PoshGitToProfile` command which will add the import statement into your `$profile` script.
- This will add the proper line to your `profile.ps1` file, and posh-git will be active the next time you open PowerShell.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Installation

**Goal:** Before you’re able to run PowerShell scripts on your machine, you need to set your local `ExecutionPolicy` to `RemoteSigned` (basically, anything except `Undefined` and `Restricted`).

**Steps:**

1. To set the value of `ExecutionPolicy` to `RemoteSigned` for all users use the next command:
   ```text
   > Set-ExecutionPolicy -Scope LocalMachine -ExecutionPolicy RemoteSigned -Force
   ```
2. More information about PowerShell Gallery: https://learn.microsoft.com/en-us/powershell/ scripting/gallery/overview.
   ```text
   > Install-Module posh-git -Scope CurrentUser -Force
   > Install-Module posh-git -Scope CurrentUser -AllowPrerelease -Force # Newer beta
   version with PowerShell Core support
   ```
3. If the second command fails with an error like `Module'PowerShellGet' was not installed by using Install-Module`, you’ll need to run another command first:
   ```text
   > Install-Module PowerShellGet -Force -SkipPublisherCheck
   ```
4. E.g. one for the console and a separate one for the ISE.
   ```text
   > Import-Module posh-git
   > Add-PoshGitToProfile -AllHosts
   ```
5. Then import the module using the full path to the `posh-git.psd1` file:
   ```text
   > Import-Module <path-to-uncompress-folder>\src\posh-git.psd1
   > Add-PoshGitToProfile -AllHosts
   ```

## Decision guide

- If you choose `AllSigned` instead of `RemoteSigned`, also local scripts (your own) need to be digitally signed in order to be executed.
- If you want to install posh-git for all users, use `-Scope AllUsers` instead and execute the command from an elevated PowerShell console.

## Related skills

- `git-installing-git` - Installing Git
- `git-scripting-github` - Scripting GitHub
- `git-configuration` - Git Configuration

## Source

"Pro Git", pages 469-471. Sections: Git in PowerShell; Git in PowerShell > Installation.
