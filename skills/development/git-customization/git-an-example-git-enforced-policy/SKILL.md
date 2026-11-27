---
name: git-an-example-git-enforced-policy
description: "Enforce commit-message format, file ACLs and push rules with git hook scripts. Use when handling a team commit or push policy."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "An Example Git-Enforced Policy"
  category: git-customization
  source: "Pro Git, 2nd edition"
  pages: "363-372"
---

# An Example Git-Enforced Policy

You’ll build client scripts that help the developer know if their push will be rejected and server scripts that actually enforce the policies.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git push -f origin master`
- Don’t judge – it’s easier to demonstrate this way.
- From now on, as long as that `update` script is there and executable, your repository will never have a commit message without your pattern in it, and your users will be sandboxed.
- The main drawback to this approach is that it can be very slow and is often unnecessary – if you don’t try to force the push with `-f`, the server will warn you and not accept the push.

## Commands

- `git cat-file`: `git cat-file commit ca82a6`
- `git commit -am`: `git commit -am 'Test'`
- `git rev-list`: `git rev-list 538c33..d14fc7`
- `git log --name-only --pretty`: `git log -1 --name-only --pretty=format:'' 9f585d`
- `git push -f`: `git push -f origin master`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error: hooks/update exited with error code 1` | There are a couple of interesting things here. |
| `! [remote rejected] master -> master (hook declined)` | You’ll see a remote rejected message for each reference that your hook declined, and it tells you that it was declined specifically because of a hook failure. |

## Related skills

- `git-hooks` - Git Hooks
- `git-configuration` - Git Configuration
- `git-as-a-client` - Git as a Client
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 363-372, CC BY-NC-SA 3.0._
