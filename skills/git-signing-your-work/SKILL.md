---
name: git-signing-your-work
description: "Signing Your Work playbook extracted from \"Pro Git\". If you’re taking work from others on the internet and want to verify that commits are actually from a trusted source, Git has a few ways to sign and verify work using GPG. Use when the user asks about signing your work, gpg signature, cryptographically secure, git merge, gpg private key, tags, command; or mentions git merge --verify-signatures, gpg --list-keys, gpg --gen-key, git config --global, git tag -s -m, git show; or hits errors like \"error: could not verify the tag 'v1.4.2.1'\"."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Signing Your Work"
  category: git-power-tools
  source: "Pro Git, 2nd edition"
  pages: "242-245"
---

# Signing Your Work

If you’re taking work from others on the internet and want to verify that commits are actually from a trusted source, Git has a few ways to sign and verify work using GPG.

_Built from "Pro Git" (pages 242-245) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **signing your work** (gpg signature, cryptographically secure, git merge, gpg private key, tags).
- The user wants to run or understand `git merge --verify-signatures`.
- The user wants to run or understand `gpg --list-keys`.
- The user wants to run or understand `gpg --gen-key`.
- The user wants to run or understand `git config --global`.
- The user sees an error like `error: could not verify the tag 'v1.4.2.1'`.
- The user sees an error like `fatal: Commit ab06180 does not have a GPG signature.`.
- If you have a GPG private key set up, you can now use it to sign new tags.

## When NOT to use

- For tagging, use the `git-tagging` skill instead.
- For maintaining a project, use the `git-distributed-git-maintaining-a-project` skill instead.
- For git configuration, use the `git-configuration` skill instead.

## Key concepts

- If you have a GPG private key set up, you can now use it to sign new tags.
- To verify a signed tag, you use `git tag -v <tag-name>`.
- If you’re interested in signing commits directly instead of just the tags, all you need to do is add a `-S` to your `git commit` command.
- If you use this option when merging a branch and it contains commits that are not signed and valid, the merge will not work.
- If the merge contains only valid signed commits, the merge command will show you all the signatures it has checked and then move forward with the merge.
- You can also use the `-S` option with the `git merge` command to sign the resulting merge commit itself.
- Signing tags and commits is great, but if you decide to use this in your normal workflow, you’ll have to make sure that everyone on your team understands how to do so.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### GPG Introduction

**Goal:** Once you have a private key to sign with, you can configure Git to use it for signing things by setting the `user.signingkey` config setting.

**Steps:**

1. First of all, if you want to sign anything you need to get GPG configured and your personal key installed.
   ```bash
   gpg --list-keys
   ```
   Expected output (excerpt):
   ```text
   /Users/schacon/.gnupg/pubring.gpg
   ---------------------------------
   pub   2048R/0A46826A 2014-06-04
   uid                  Scott Chacon (Git signing key) <schacon@gmail.com>
   ```
2. If you don’t have a key installed, you can generate one with `gpg --gen-key`.
   ```bash
   gpg --gen-key
   ```
3. Once you have a private key to sign with, you can configure Git to use it for signing things by setting the `user.signingkey` config setting.
   ```bash
   git config --global user.signingkey 0A46826A!
   ```

### Signing Tags

**Goal:** If you have a GPG private key set up, you can now use it to sign new tags.

**Steps:**

1. All you have to do is use `-s` instead of `-a`:
   ```bash
   git tag -s v1.5 -m 'my signed 1.5 tag'
   ```
   Expected output (excerpt):
   ```text
   You need a passphrase to unlock the secret key for
   user: "Ben Straub <ben@straub.cc>"
   2048-bit RSA key, ID 800430EB, created 2014-05-04
   ```
2. If you run `git show` on that tag, you can see your GPG signature attached to it:
   ```bash
   git show v1.5
   ```
   Expected output (excerpt):
   ```text
   tag v1.5
   Tagger: Ben Straub <ben@straub.cc>
   ```
3. Run:
   ```text
   Date:   Sat May 3 20:29:41 2014 -0700
   my signed 1.5 tag
   -----BEGIN PGP SIGNATURE-----
   Version: GnuPG v1
   iQEcBAABAgAGBQJTZbQlAAoJEF0+sviABDDrZbQH/09PfE51KPVPlanr6q1v4/Ut
   LQxfojUWiLQdg2ESJItkcuweYg+kc3HCyFejeDIBw9dpXt00rY26p05qrpnG+85b
   hM1/PswpPLuBSr+oCIDj5GMC2r2iEKsfv2fJbNW8iWAXVLoWZRF8B0MfqX/YTMbm
   ecorc4iXzQu7tupRihslbNkfvfciMnSDeSvzCpWAHl7h8Wj6hhqePmLm9lAYqnKp
   8S5B/1SSQuEAjRZgI4IexpZoeKGVDptPHxLLS38fozsyi0QyDyzEgJxcJQVMXxVi
   RUysgqjcpT8+iQM1PblGfHR4XAhuOqN5Fx06PSaFZhqvWFezJ28/CLyX5q+oIVk=
   =EFTF
   -----END PGP SIGNATURE-----
   commit ca82a6dff817ec66f44342007202690a93763949
   Author: Scott Chacon <schacon@gee-mail.com>
   Date:   Mon Mar 17 21:52:11 2008 -0700
   # ... (full listing in references)
   ```

**Verify:** run `git show v1.5` - expect something like:
```text
tag v1.5
Tagger: Ben Straub <ben@straub.cc>
```

### Verifying Tags

**Goal:** To verify a signed tag, you use `git tag -v <tag-name>`.

**Steps:**

1. You need the signer’s public key in your keyring for this to work properly:
   ```bash
   git tag -v v1.4.2.1
   ```
   Expected output (excerpt):
   ```text
   object 883653babd8ee7ea23e6a5c392bb739348b1eb61
   type commit
   tag v1.4.2.1
   tagger Junio C Hamano <junkio@cox.net> 1158138501 -0700
   ```
2. If you don’t have the signer’s public key, you get something like this instead:
   ```text
   gpg: Signature made Wed Sep 13 02:08:25 2006 PDT using DSA key ID F3119B9A
   gpg: Can't check signature: public key not found
   error: could not verify the tag 'v1.4.2.1'
   ```

### Signing Commits

**Goal:** In more recent versions of Git (v1.7.9 and above), you can now also sign individual commits.

**Steps:**

1. If you’re interested in signing commits directly instead of just the tags, all you need to do is add a `-S` to your `git commit` command.
   ```bash
   git commit -a -S -m 'Signed commit'
   ```
   Expected output (excerpt):
   ```text
   You need a passphrase to unlock the secret key for
   user: "Scott Chacon (Git signing key) <schacon@gmail.com>"
   2048-bit RSA key, ID 0A46826A, created 2014-06-04
   [master 5c3386c] Signed commit
   ```
2. To see and verify these signatures, there is also a `--show-signature` option to `git log`.
   ```bash
   git log --show-signature -1
   ```
   Expected output (excerpt):
   ```text
   commit 5c3386cf54bba0a33a32da706aa52bc0155503c2
   gpg: Signature made Wed Jun  4 19:49:17 2014 PDT using RSA key ID 0A46826A
   gpg: Good signature from "Scott Chacon (Git signing key) <schacon@gmail.com>"
   Author: Scott Chacon <schacon@gmail.com>
   ```
3. Additionally, you can configure `git log` to check any signatures it finds and list them in its output with the `%G?` format.
   ```bash
   git log --pretty="format:%h %G? %aN  %s"
   ```
   Expected output (excerpt):
   ```text
   5c3386c G Scott Chacon  Signed commit
   ca82a6d N Scott Chacon  Change the version number
   085bb3b N Scott Chacon  Remove unnecessary test code
   a11bef0 N Scott Chacon  Initial commit
   ```
4. If you use this option when merging a branch and it contains commits that are not signed and valid, the merge will not work.
   ```bash
   git merge --verify-signatures non-verify
   ```
5. Run:
   ```text
   fatal: Commit ab06180 does not have a GPG signature.
   ```
6. If the merge contains only valid signed commits, the merge command will show you all the signatures it has checked and then move forward with the merge.
   ```bash
   git merge --verify-signatures signed-branch
   ```
   Expected output (excerpt):
   ```text
   Commit 13ad65e has a good GPG signature by Scott Chacon (Git signing key)
   <schacon@gmail.com>
   Updating 5c3386c..13ad65e
   Fast-forward
   ```

_1 more step(s) in references/procedures.md._

**Verify:** run `git log --pretty="format:%h %G? %aN  %s"` - expect something like:
```text
5c3386c G Scott Chacon  Signed commit
ca82a6d N Scott Chacon  Change the version number
085bb3b N Scott Chacon  Remove unnecessary test code
a11bef0 N Scott Chacon  Initial commit
```

More procedures in [references/procedures.md](references/procedures.md):

- Signing Tags
- Signing Commits

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git merge --verify-signatures` | If you use this option when merging a branch and it contains commits that are not signed and valid, the merge will not work. | `git merge --verify-signatures non-verify` |
| `gpg --list-keys` | First of all, if you want to sign anything you need to get GPG configured and your personal key installed. | `gpg --list-keys` |
| `gpg --gen-key` | If you don’t have a key installed, you can generate one with `gpg --gen-key`. | `gpg --gen-key` |
| `git config --global` | Once you have a private key to sign with, you can configure Git to use it for signing things by setting the `user.signingkey` config setting. | `git config --global user.signingkey 0A46826A!` |
| `git tag -s -m` | All you have to do is use `-s` instead of `-a` | `git tag -s v1.5 -m 'my signed 1.5 tag'` |
| `git show` | If you run `git show` on that tag, you can see your GPG signature attached to it | `git show v1.5` |
| `git tag -v` | To verify a signed tag, you use `git tag -v <tag-name>`. | `git tag -v v1.4.2.1` |
| `git commit -a -S` | If you’re interested in signing commits directly instead of just the tags, all you need to do is add a `-S` to your `git commit` command. | `git commit -a -S -m 'Signed commit'` |
| `git log --show-signature` | To see and verify these signatures, there is also a `--show-signature` option to `git log`. | `git log --show-signature -1` |
| `git log --pretty` | Additionally, you can configure `git log` to check any signatures it finds and list them in its output with the `%G?` format. | `git log --pretty="format:%h %G? %aN  %s"` |
| `git merge --verify-signatures -S` | The following example both verifies that every commit in the branch to be merged is signed and furthermore signs the resulting merge commit. | `git merge --verify-signatures -S  signed-branch` |

## Decision guide

- If you’re interested in signing commits directly instead of just the tags, all you need to do is add a `-S` to your `git commit` command.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error: could not verify the tag 'v1.4.2.1'` | See references/source-text.md for this section. |
| `fatal: Commit ab06180 does not have a GPG signature.` | If the merge contains only valid signed commits, the merge command will show you all the signatures it has checked and then move forward with the merge. |


## Related skills

- `git-tagging` - Tagging
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-configuration` - Git Configuration
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project

## Source

"Pro Git", pages 242-245. Sections: Signing Your Work; Signing Your Work > GPG Introduction; Signing Your Work > Signing Tags; Signing Your Work > Verifying Tags; Signing Your Work > Signing Commits; Signing Your Work > Everyone Must Sign.
