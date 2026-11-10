---
name: git-distributed-git-maintaining-a-project
description: "Maintaining a Project playbook extracted from \"Pro Git\". This can consist of accepting and applying patches generated via format-patch and emailed to you, or integrating changes in remote branches for repositories you’ve added as remotes to your project. Use when the user asks about maintaining a project, topic branch, git apply, git project, master, work, command; or mentions git diff, git am, git checkout -b, git branch, git apply, git apply --check; or hits errors like \"error: patch failed: ticgit.gemspec:1\"."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Maintaining a Project"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "156-171"
---

# Maintaining a Project

This can consist of accepting and applying patches generated via `format-patch` and emailed to you, or integrating changes in remote branches for repositories you’ve added as remotes to your project.

_Built from "Pro Git" (pages 156-171) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **maintaining a project** (topic branch, git apply, git project, master, work).
- The user wants to run or understand `git diff`.
- The user wants to run or understand `git am`.
- The user wants to run or understand `git checkout -b`.
- The user wants to run or understand `git branch`.
- The user sees an error like `error: patch failed: ticgit.gemspec:1`.
- The user sees an error like `error: ticgit.gemspec: patch does not apply`.

## When NOT to use

- For contributing to a project, use the `git-distributed-git-contributing-to-a-project` skill instead.
- For maintaining a project, use the `git-github-maintaining-a-project` skill instead.
- For contributing to a project, use the `git-github-contributing-to-a-project` skill instead.

## Key concepts

- If you receive a patch over email that you need to integrate into your project, you need to apply the patch in your topic branch to evaluate it.
- What you really want to see are the changes added to the topic branch — the work you’ll introduce if you merge this branch with `master`.
- Each time you have a new topic branch to merge in (Before a topic branch merge), you merge it into `develop` (After a topic branch merge); then, when you tag a release, you fast-forward `master` to wherever the now-stable `develop` branch is (After a project release).
- This way, when people clone your project’s repository, they can either check out `master` to build the latest stable version and keep up to date on that easily, or they can check out `develop`, which is the more cutting-edge content.
- When new work is introduced by contributors, it’s collected into topic branches in the maintainer’s repository in a manner similar to what we’ve described (see Managing a complex series of parallel contributed topic branches).
- Other maintainers prefer to rebase or cherry-pick contributed work on top of their `master` branch, rather than merging it in, to keep a mostly linear history.
- If you’re doing lots of merging and rebasing, or you’re maintaining a long-lived topic branch, Git has a feature called “rerere” that can help.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- That is probably the simplest workflow, but it can possibly be problematic if you’re dealing with larger or more stable projects where you want to be really careful about what you introduce.

## Procedures

### Working in Topic Branches

**Goal:** The maintainer of the Git project tends to namespace these branches as well — such as `sc/ruby_client`, where `sc` is short for the person who contributed the work.

**Steps:**

1. As you’ll remember, you can create the branch based off your `master` branch like this:
   ```bash
   git branch sc/ruby_client master
   ```
2. Or, if you want to also switch to it immediately, you can use the `checkout -b` option:
   ```bash
   git checkout -b sc/ruby_client master
   ```

### Applying Patches from Email

**Goal:** If you receive a patch over email that you need to integrate into your project, you need to apply the patch in your topic branch to evaluate it.

**Steps:**

1. Assuming you saved the patch at `/tmp/patch-ruby-client.patch`, you can apply the patch like this:
   ```bash
   git apply /tmp/patch-ruby-client.patch
   ```
2. You can also use `git apply` to see if a patch applies cleanly before you try actually applying it — you can run `git apply --check` with the patch:
   ```bash
   git apply --check 0001-see-if-this-helps-the-gem.patch
   ```
   Expected output (excerpt):
   ```text
   error: patch failed: ticgit.gemspec:1
   error: ticgit.gemspec: patch does not apply
   ```
3. It looks something like this:
   ```text
   From 330090432754092d704da8e76ca5c05c198e71a8 Mon Sep 17 00:00:00 2001
   From: Jessica Smith <jessica@example.com>
   Date: Sun, 6 Apr 2008 10:17:23 -0700
   Subject: [PATCH 1/2] Add limit to log function
   Limit log functionality to the first 20
   ```
4. However, if someone uploaded a patch file generated via `git format-patch` to a ticketing system or something similar, you can save the file locally and then pass that file saved on your disk to `git am` to apply it:
   ```bash
   git am 0001-limit-log-function.patch
   ```
   Expected output (excerpt):
   ```text
   Applying: Add limit to log function
   ```
5. For example, if this patch was applied from the mbox example above, the commit generated would look something like this:
   ```bash
   git log --pretty=fuller -1
   ```
   Expected output (excerpt):
   ```text
   commit 6c5e70b984a60b3cecd395edd5b48a7575bf58e0
   Author:     Jessica Smith <jessica@example.com>
   AuthorDate: Sun Apr 6 10:17:23 2008 -0700
   Commit:     Scott Chacon <schacon@gmail.com>
   ```
6. In that case, the `git am` process will fail and ask you what you want to do:
   ```bash
   git am 0001-see-if-this-helps-the-gem.patch
   ```
   Expected output (excerpt):
   ```text
   Applying: See if this helps the gem
   error: patch failed: ticgit.gemspec:1
   error: ticgit.gemspec: patch does not apply
   Patch failed at 0001.
   ```

_4 more step(s) in references/procedures.md._

**Verify:** run `git log --pretty=fuller -1` - expect something like:
```text
commit 6c5e70b984a60b3cecd395edd5b48a7575bf58e0
Author:     Jessica Smith <jessica@example.com>
AuthorDate: Sun Apr 6 10:17:23 2008 -0700
Commit:     Scott Chacon <schacon@gmail.com>
CommitDate: Thu Apr 9 09:19:06 2009 -0700
   Add limit to log function
```

**If it fails:** Finally, `git apply` is an “apply all or abort all” model where either everything is applied or nothing is, whereas `patch` can partially apply patchfiles, leaving your working directory in a weird state.

### Checking Out Remote Branches

**Goal:** Checking Out Remote Branches

**Steps:**

1. For instance, if Jessica sends you an email saying that she has a great new feature in the `ruby-client` branch of her repository, you can test it by adding the remote and checking out that branch locally:
   ```bash
   git remote add jessica https://github.com/jessica/myproject.git
   git fetch jessica
   git checkout -b rubyclient jessica/ruby-client
   ```
2. This does a one-time pull and doesn’t save the URL as a remote reference:
   ```bash
   git pull https://github.com/onetimeguy/project
   ```
   Expected output (excerpt):
   ```text
   From https://github.com/onetimeguy/project
    * branch            HEAD       -> FETCH_HEAD
   Merge made by the 'recursive' strategy.
   ```

### Tagging Your Releases

**Goal:** The maintainer of the Git project has solved this issue by including their public key as a blob in the repository and then adding a tag that points directly to that content.

**Steps:**

1. If you decide to sign the tag as the maintainer, the tagging may look something like this:
   ```bash
   git tag -s v1.5 -m 'my signed 1.5 tag'
   ```
   Expected output (excerpt):
   ```text
   You need a passphrase to unlock the secret key for
   user: "Scott Chacon <schacon@gmail.com>"
   1024-bit DSA key, ID F721C45A, created 2009-02-09
   ```
2. To do this, you can figure out which key you want by running `gpg --list-keys`:
   ```bash
   gpg --list-keys
   ```
   Expected output (excerpt):
   ```text
   /Users/schacon/.gnupg/pubring.gpg
   ---------------------------------
   pub   1024D/F721C45A 2009-02-09 [expires: 2010-02-09]
   uid                  Scott Chacon <schacon@gmail.com>
   ```
3. Then, you can directly import the key into the Git database by exporting it and piping that through `git hash-object`, which writes a new blob with those contents into Git and gives you back the SHA-1 of the blob:
   ```bash
   gpg -a --export F721C45A | git hash-object -w --stdin
   ```
   Expected output (excerpt):
   ```text
   659ef797d181633c87ec71ac3f9ba29fe5775b92
   ```
4. Now that you have the contents of your key in Git, you can create a tag that points directly to it by specifying the new SHA-1 value that the `hash-object` command gave you:
   ```bash
   git tag -a maintainer-pgp-pub 659ef797d181633c87ec71ac3f9ba29fe5775b92
   ```
5. If anyone wants to verify a tag, they can directly import your PGP key by pulling the blob directly out of the database and importing it into GPG:
   ```bash
   git show maintainer-pgp-pub | gpg --import
   ```

**Verify:** run `git show maintainer-pgp-pub | gpg --import`

### Preparing a Release

**Goal:** If someone opens that tarball, they get the latest snapshot of your project under a `project` directory.

**Steps:**

1. The command to do this is `gitarchive`:
   ```bash
   git archive master --prefix='project/' | gzip > `git describe master`.tar.gz
   ls *.tar.gz
   ```
   Expected output (excerpt):
   ```text
   v1.6.2-rc1-20-g8c5b85c.tar.gz
   ```
2. You can also create a zip archive in much the same way, but by passing the `--format=zip` option to `git archive`:
   ```bash
   git archive master --prefix='project/' --format=zip > `git describe master`.zip
   ```

More procedures in [references/procedures.md](references/procedures.md):

- Applying Patches from Email
- Determining What Is Introduced
- Integrating Contributed Work
- Generating a Build Number
- The Shortlog

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git diff` | If you received the patch from someone who generated it with `git diff` or some variation of the | `git diff master` |
| `git am` | Technically, `git am` is built to read an mbox file, which is a simple, plain-text format for storing one or more email messages in one text file. | `git am 0001-limit-log-function.patch` |
| `git checkout -b` | Or, if you want to also switch to it immediately, you can use the `checkout -b` option | `git checkout -b sc/ruby_client master` |
| `git branch` | As you’ll remember, you can create the branch based off your `master` branch like this | `git branch sc/ruby_client master` |
| `git apply` | Finally, `git apply` is an “apply all or abort all” model where either everything is applied or nothing is, whereas `patch` can partially apply patchfiles, leaving your working directory in a weird state. | `git apply /tmp/patch-ruby-client.patch` |
| `git apply --check` | You can also use `git apply` to see if a patch applies cleanly before you try actually applying it — you can run `git apply --check` with the patch | `git apply --check 0001-see-if-this-helps-the-gem.patch` |
| `git log --pretty` | For example, if this patch was applied from the mbox example above, the commit generated would look something like this | `git log --pretty=fuller -1` |
| `(fix the` | You solve this issue much the same way — edit the file to resolve the conflict, stage the new file, and then run `git am --resolved` to continue to the next patch | `(fix the file)` |
| `git add` | You solve this issue much the same way — edit the file to resolve the conflict, stage the new file, and then run `git am --resolved` to continue to the next patch | `git add ticgit.gemspec` |
| `git am --resolved` | You solve this issue much the same way — edit the file to resolve the conflict, stage the new file, and then run `git am --resolved` to continue to the next patch | `git am --resolved` |
| `git am -i` | If you’re applying a number of patches from an mbox, you can also run the `am` command in interactive mode, which stops at each patch it finds and asks if you want to apply it | `git am -3 -i mbox` |
| `git remote` | For instance, if Jessica sends you an email saying that she has a great new feature in the `ruby-client` branch of her repository, you can test it by adding the remote and checking out that branch locally | `git remote add jessica https://github.com/jessica/myproject.git` |
| `git fetch` | For instance, if Jessica sends you an email saying that she has a great new feature in the `ruby-client` branch of her repository, you can test it by adding the remote and checking out that branch locally | `git fetch jessica` |
| `git pull` | If you aren’t working with a person consistently but still want to pull from them in this way, you can provide the URL of the remote repository to the `git pull` command. | `git pull https://github.com/onetimeguy/project` |
| `git log --not` | For example, if your contributor sends you two patches and you create a branch called `contrib` and applied those patches there, you can run this | `git log contrib --not master` |
| `git merge-base` | Technically, you can do that by explicitly figuring out the common ancestor and then running your diff on it | `git merge-base contrib master` |
| `git cherry-pick` | If you want to pull commit `e43a6` into your `master` branch, you can run | `git cherry-pick e43a6` |
| `git config --global` | The configuration setting is `rerere.enabled`, and it’s handy enough to put in your global config | `git config --global rerere.enabled true` |
| `git tag -s -m` | If you decide to sign the tag as the maintainer, the tagging may look something like this | `git tag -s v1.5 -m 'my signed 1.5 tag'` |
| `gpg --list-keys` | To do this, you can figure out which key you want by running `gpg --list-keys` | `gpg --list-keys` |

## Decision guide

- When you’re thinking of integrating new work, it’s generally a good idea to try it out in a topic branch — a temporary branch specifically made to try out that new work.
- If there is no output, then the patch should apply cleanly.
- If you can, encourage your contributors to use `format-patch` instead of `diff` to generate patches for you.
- If they’re safe, they’re merged into `next`, and that branch is pushed up so everyone can try the topics integrated together.
- If the topics still need work, they’re merged into `seen` instead.
- Other maintainers prefer to rebase or cherry-pick contributed work on top of their `master` branch, rather than merging it in, to keep a mostly linear history.
- This is useful if you have a number of commits on a topic branch and you want to integrate only one of them, or if you only have one commit on a topic branch and you’d prefer to cherry-pick it rather than run rebase.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error: patch failed: ticgit.gemspec:1` | If there is no output, then the patch should apply cleanly. |
| `error: ticgit.gemspec: patch does not apply` | In this case, without the `-3` option the patch would have been considered as a conflict. |


## Related skills

- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-github-maintaining-a-project` - Maintaining a Project
- `git-github-contributing-to-a-project` - Contributing to a Project
- `git-rebasing` - Rebasing

## Source

"Pro Git", pages 156-171. Sections: Maintaining a Project; Maintaining a Project > Working in Topic Branches; Maintaining a Project > Applying Patches from Email; Maintaining a Project > Checking Out Remote Branches; Maintaining a Project > Determining What Is Introduced; Maintaining a Project > Integrating Contributed Work; Maintaining a Project > Tagging Your Releases; Maintaining a Project > Generating a Build Number; Maintaining a Project > Preparing a Release; Maintaining a Project > The Shortlog.
