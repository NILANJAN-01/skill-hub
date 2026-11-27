---
name: git-submodules
description: "Use git submodules: add, clone --recurse-submodules, update, publish. Use when a repo contains another repo or submodule folders are empty."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Submodules"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "304-324"
---

# Submodules

Although `DbConnector` is a subdirectory in your working directory, Git sees it as a submodule and doesn’t track its contents when you’re not in that directory.

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git submodule update --remote --rebase`
  - `git clean -ffdx`
  - `git rm -r CryptoLibrary`
- **Note (from source):** Since the URL in the .gitmodules file is what other people will first try to clone/fetch from, make sure to use a URL that they can access if possible. For example, if you use a different URL to push to than others would to pull from, use the one that others have access to. You can overwrite this value locally with `gitconfig submodule.DbConnector.url PRIVATE_URL` for your own use. When applicable, a relative URL can be helpful.
- With no working branch tracking changes, that means even if you commit changes to the submodule, those changes will quite possibly be lost the next time you run `git submodule update`.
- If you haven’t committed your changes in your submodule and you run a `submodule update` that would cause issues, Git will fetch the changes but not overwrite unsaved work in your submodule directory.

## Commands

- `git submodule`: `git submodule init`
- `git status`
- `git commit -am`: `git commit -am 'Unicode support'`
- `git diff`
- `git merge`: `git merge 9fd905e`
- `git submodule --remote`: `git submodule update --remote`
- `git checkout`: `git checkout stable`
- `git add`: `git add src/main.c`
- `git config`: `git config status.submodulesummary 1`
- `git pull`
- `git submodule --init --recursive`: `git submodule update --init --recursive`
- `git submodule --remote --merge`: `git submodule update --remote --merge`

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error: Your local changes to the following files would be overwritten by checkout:` | If you made changes that conflict with something changed upstream, Git will let you know when you run the update. |
| `CONFLICT (content): Merge conflict in scripts/setup.sh` | You can go into the submodule directory and fix the conflict just as you normally would. |
| `warning: Failed to merge submodule DbConnector (merge following commits not found)` | So basically what has happened here is that Git has figured out that the two branches record points in the submodule’s history that are divergent and need to be merged. |
| `CONFLICT (content): Merge conflict in src/main.c` | We got an actual merge conflict here, so if we resolve that and commit it, then we can simply update the main project with the result. |
| `warning: Failed to merge submodule DbConnector (not fast-forward)` | The suggested command Git is providing will update the index as though you had run `git add` (which clears the conflict), then commit. |
| `warning: unable to rmdir CryptoLibrary: Directory not empty` | Removing the directory isn’t difficult, but it can be a bit confusing to have that in there. |
| `error: The following untracked working tree files would be overwritten by checkout:` | You can force it to switch with `checkout -f`, but be careful that you don’t have unsaved changes in there as they could be overwritten with that command. |

## Related skills

- `git-advanced-merging` - Advanced Merging
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-recording-changes-to-the-repository` - Recording Changes to the Repository
- `git-as-a-client` - Git as a Client

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 304-324, CC BY-NC-SA 3.0._
