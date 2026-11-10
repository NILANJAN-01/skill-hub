---
name: git-github-maintaining-a-project
description: "Maintaining a Project playbook extracted from \"Pro Git\". Doing so will give them “push” access, which means they have both read and write access to the project and Git repository. Use when the user asks about maintaining a project, pull request, git pull; or mentions git fetch, curl, git ls-remote, git checkout."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Maintaining a Project"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "197-211"
---

# Maintaining a Project

Doing so will give them “push” access, which means they have both read and write access to the project and Git repository.

_Built from "Pro Git" (pages 197-211) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **maintaining a project** (pull request, git pull).
- The user wants to run or understand `git fetch`.
- The user wants to run or understand `curl`.
- The user wants to run or understand `git ls-remote`.
- The user wants to run or understand `git checkout`.
- If you want to highlight or re-route emails to this particular project or even Pull Request, the information in `Message-ID` gives you all the data in `<user>/<project>/<type>/<id>` format.
- If you would like to transfer a project to another user or an organization in GitHub, there is a “Transfer ownership” option at the bottom of the same “Options” tab of your repository settings page that allows you to do this.

## When NOT to use

- For contributing to a project, use the `git-github-contributing-to-a-project` skill instead.
- For maintaining a project, use the `git-distributed-git-maintaining-a-project` skill instead.
- For contributing to a project, use the `git-distributed-git-contributing-to-a-project` skill instead.

## Key concepts

- Git repository, or connect an existing Git project.
- This means that we can pretty easily pull down every Pull Request branch in one go without having to add a bunch of remotes.
- When you go to open a Pull Request, there is a box at the top of the page that specifies which branch you’re requesting to pull to and which you’re requesting to pull from.
- Email notifications are the other way you can handle notifications through GitHub.
- If you want to highlight or re-route emails to this particular project or even Pull Request, the information in `Message-ID` gives you all the data in `<user>/<project>/<type>/<id>` format.
- The idea here is that you can specify specific things you want or don’t want in a Pull Request sent to your project.
- If you would like to transfer a project to another user or an organization in GitHub, there is a “Transfer ownership” option at the bottom of the same “Options” tab of your repository settings page that allows you to do this.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Managing Pull Requests

**Goal:** For these examples, let’s assume you are “tonychacon” and you’ve created a new Arduino code project named “fade”.

**Steps:**

1. You could technically merge in the Pull Request work with something like this:
   ```bash
   curl https://github.com/tonychacon/fade/pull/1.patch | git am
   ```
2. If we run this command against the “blink” repository we were using earlier, we will get a list of all the branches and tags and other references in the repository.
   ```bash
   git ls-remote https://github.com/schacon/blink
   ```
   Expected output (excerpt):
   ```text
   10d539600d86723087810ec636870a504f4fee4d    HEAD
   10d539600d86723087810ec636870a504f4fee4d    refs/heads/master
   6a83107c62950be9453aac297bb0193fd743cd6e    refs/pull/1/head
   afe83c2d1a70674c9505cc1d8b7d380d5e076ed3    refs/pull/1/merge
   ```
3. Now, you could do something like fetching the reference directly.
   ```bash
   git fetch origin refs/pull/958/head
   ```
   Expected output (excerpt):
   ```text
   From https://github.com/libgit2/libgit2
    * branch            refs/pull/958/head -> FETCH_HEAD
   ```
4. It should look a bit like this:
   ```ini
   [remote "origin"]
       url = https://github.com/libgit2/libgit2
       fetch = +refs/heads/*:refs/remotes/origin/*
   ```
5. That line that begins with `fetch =` is a “refspec.” It’s a way of mapping names on the remote with names in your local `.git` directory.
   ```ini
   [remote "origin"]
       url = https://github.com/libgit2/libgit2.git
       fetch = +refs/heads/*:refs/remotes/origin/*
       fetch = +refs/pull/*/head:refs/remotes/origin/pr/*
   ```
6. That last line tells Git, “All the refs that look like `refs/pull/123/head` should be stored locally like `refs/remotes/origin/pr/123`.” Now, if you save that file, and do a `git fetch`:
   ```bash
   git fetch
   ```
   Expected output (excerpt):
   ```text
   # …
    * [new ref]         refs/pull/1/head -> origin/pr/1
    * [new ref]         refs/pull/2/head -> origin/pr/2
    * [new ref]         refs/pull/4/head -> origin/pr/4
   ```

_1 more step(s) in references/procedures.md._

**Verify:** run `git ls-remote https://github.com/schacon/blink` - expect something like:
```text
10d539600d86723087810ec636870a504f4fee4d    HEAD
10d539600d86723087810ec636870a504f4fee4d    refs/heads/master
6a83107c62950be9453aac297bb0193fd743cd6e    refs/pull/1/head
afe83c2d1a70674c9505cc1d8b7d380d5e076ed3    refs/pull/1/merge
3c8d735ee16296c242be7a9742ebfbc2665adec1    refs/pull/2/head
15c9f4f80973a2758462ab2066b6ad9fe8dcf03d    refs/pull/2/merge
```

**If it fails:** So if someone opens a Pull Request in our repository and their branch is named `bug-fix` and it points to commit `a5a775`, then in our repository we will not have a `bug-fix` branch (since that’s in their fork), but we will have `pull/<pr#>/head` that points to `a5a775`.

### Mentions and Notifications

**Goal:** If you want to highlight or re-route emails to this particular project or even Pull Request, the information in `Message-ID` gives you all the data in `<user>/<project>/<type>/<id>` format.

**Steps:**

1. For instance, if we look at the actual email headers sent to Tony in the email shown in Email notification of a new Pull Request, we will see the following among the information sent:
   ```text
   To: tonychacon/fade <fade@noreply.github.com>
   Message-ID: <tonychacon/fade/pull/1@github.com>
   Subject: [fade] Wait longer to see the dimming effect better (#1)
   X-GitHub-Recipient: tonychacon
   List-ID: tonychacon/fade <fade.tonychacon.github.com>
   List-Archive: https://github.com/tonychacon/fade
   List-Post: <mailto:reply+i-4XXX@reply.github.com>
   List-Unsubscribe: <mailto:unsub+i-XXX@reply.github.com>,...
   X-GitHub-Recipient-Address: tchacon@example.com
   ```

More procedures in [references/procedures.md](references/procedures.md):

- Managing Pull Requests

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git fetch` | That last line tells Git, “All the refs that look like `refs/pull/123/head` should be stored locally like `refs/remotes/origin/pr/123`.” Now, if you save that file, and do a `git fetch` | `git fetch` |
| `curl` | You could technically merge in the Pull Request work with something like this | `curl https://github.com/tonychacon/fade/pull/1.patch \| git am` |
| `git ls-remote` | Of course, if you’re in your repository and you run `git ls-remote origin` or whatever remote you want to check, it will show you something similar to this. | `git ls-remote https://github.com/schacon/blink` |
| `git checkout` | This makes it super easy to try the code from a pull request locally | `git checkout pr/2` |

## Decision guide

- If you see a Pull Request that is moving in the right direction and you have an idea for a change that depends on it or you’re not sure is a good idea, or you just don’t have push access to the target branch, you can open a Pull Request directly to it.
- If you have this option selected in your preferences and a notification is triggered for you, you will see a small blue dot over your notifications icon at the top of your screen as seen in Notification center.

## Troubleshooting

- **Note:** It is often preferable to share the HTTPS based URL for a public project, since the user does not have to have a GitHub account to access it for cloning. Users will have to have an account and an uploaded SSH key to access your project if you give them the SSH URL. The HTTPS one is also exactly the same URL they would paste into a browser to view the project there.

## Related skills

- `git-github-contributing-to-a-project` - Contributing to a Project
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-scripting-github` - Scripting GitHub

## Source

"Pro Git", pages 197-211. Sections: Maintaining a Project; Maintaining a Project > Creating a New Repository; Maintaining a Project > Adding Collaborators; Maintaining a Project > Managing Pull Requests; Maintaining a Project > Mentions and Notifications; Maintaining a Project > Special Files; Maintaining a Project > README; Maintaining a Project > CONTRIBUTING; Maintaining a Project > Project Administration.
