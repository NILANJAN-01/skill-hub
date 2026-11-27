---
name: git-libgit2
description: "Use git from C, Ruby, .NET or Python through libgit2 bindings. Use when you need to embed git operations in an application."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Libgit2"
  category: git-integrations
  source: "Pro Git, 2nd edition"
  pages: "472-477"
---

# Libgit2

Objective-Git (https://github.com/libgit2/objective-git) is the name of the

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error = git_revparse_single(&head_commit, repo, "HEAD^{commit}");` | The first couple of lines open a Git repository. |
| `error = git_odb_backend_mine(&my_backend, /*…*/); ②` | Note that errors are captured, but not handled. |
| `error:NULL];` | Objective-git is fully interoperable with Swift, so don’t fear if you’ve left Objective-C behind. |

## Related skills

- `git-scripting-github` - Scripting GitHub
- `git-jgit` - JGit
- `git-getting-a-git-repository` - Getting a Git Repository
- `git-objects` - Git Objects

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 472-477, CC BY-NC-SA 3.0._
