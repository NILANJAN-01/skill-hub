---
name: git-hooks
description: "Git Hooks playbook extracted from \"Pro Git\". This hook takes a few parameters: the path to the file that holds the commit message so far, the type of commit, and the commit SHA-1 if this is an amended commit. Use when the user asks about git hooks, hook runs, commit message, git commit, client-side hooks, push, version control systems."
---

# Git Hooks

This hook takes a few parameters: the path to the file that holds the commit message so far, the type of commit, and the commit SHA-1 if this is an amended commit.

_Built from "Pro Git" (pages 360-363) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **git hooks** (hook runs, commit message, git commit, client-side hooks, push).
- You can use these hooks for all sorts of reasons.
- If you want to use the bundled hook scripts, you’ll have to rename them; their file names all end with `.sample`.
- You can use this hook to disallow rebasing any commits that have already been pushed.
- After you run a successful `git checkout`, the `post-checkout` hook runs; you can use it to set up your working directory properly for your project environment.
- In addition to the client-side hooks, you can use a couple of important server-side hooks as a system administrator to enforce nearly any kind of policy for your project.

## When NOT to use

- For an example git-enforced policy, use the `git-an-example-git-enforced-policy` skill instead.
- For scripting github, use the `git-scripting-github` skill instead.
- For git as a client, use the `git-as-a-client` skill instead.

## Key concepts

- Client-side hooks are triggered by operations such as committing and merging, while server-side hooks run on network operations such as receiving pushed commits.
- The `pre-commit` hook is run first, before you even type in a commit message.
- Exiting non-zero from this hook aborts the commit, although you can bypass it with `git commit --no-verify`.
- The `commit-msg` hook takes one parameter, which again is the path to a temporary file that contains the commit message written by the developer.
- After the entire commit process is completed, the `post-commit` hook runs.
- The last hook to run during a `git am` operation is `post-applypatch`, which runs after the commit is made.
- The `post-rewrite` hook is run by commands that replace commits, such as `git commit --amend` and `git rebase` (though not by `git filter-branch`).

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- This script can’t stop the push process, but the client doesn’t disconnect until it has completed, so be careful if you try to do anything that may take a long time.

## Decision guide

- Instead of reading from stdin, this script takes three arguments: the name of the reference (branch), the SHA-1 that reference pointed to before the push, and the SHA-1 the user is trying to push.

## Troubleshooting

- **Note:** It’s important to note that client-side hooks are not copied when you clone a repository. If your intent with these scripts is to enforce a policy, you’ll probably want to do that on the server side; see the example in An Example Git-Enforced Policy.
- **Tip:** If you’re writing a script/hook that others will need to read, prefer the long versions of command-line flags; six months from now you’ll thank us.

## Related skills

- `git-an-example-git-enforced-policy` - An Example Git-Enforced Policy
- `git-scripting-github` - Scripting GitHub
- `git-as-a-client` - Git as a Client
- `git-configuration` - Git Configuration

## Source

"Pro Git", pages 360-363. Sections: Git Hooks; Git Hooks > Installing a Hook; Git Hooks > Client-Side Hooks; Git Hooks > Server-Side Hooks.
