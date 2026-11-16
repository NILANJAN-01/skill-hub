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

_Built from "Pro Git" (pages 304-324) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **submodules** (git submodule update, submodule directory, git diff, main project, commits).
- The user wants to run or understand `git submodule`.
- The user wants to run or understand `git submodule --remote`.
- The user wants to run or understand `git submodule --init --recursive`.
- The user wants to run or understand `git submodule --remote --merge`.
- The user sees an error like `error: Your local changes to the following files would be overwritten by checkout:`.
- The user sees an error like `CONFLICT (content): Merge conflict in scripts/setup.sh`.
- The user sees an error like `warning: Failed to merge submodule DbConnector (merge following commits not found)`.
- To also initialize, fetch and checkout any nested submodules, you can use the foolproof `git submoduleupdate --init --recursive`.
- If you want to check for new work in a submodule, you can go into the directory and run `git fetch` and `git merge` the upstream branch to update the local code.
- If you want to automate this process, you can add the `--recurse-submodules` flag to the `git pull` command (since Git 2.14).
- Moreover, if you want to make Git always pull with `--recurse-submodules`, you can set the configuration option `submodule.recurse` to `true` (this works for `git pull` since Git 2.15).
- This way you can simply run `git supdate` when you want to update your submodules, or `git spush` to push with submodule dependency checking.

## When NOT to use

- If you don’t want to type `--submodule` every time you run `git diff`, you can set it as the default format by setting the `diff.submodule` config value to “log”.
- For advanced merging, use the `git-advanced-merging` skill instead.
- For contributing to a project, use the `git-distributed-git-contributing-to-a-project` skill instead.
- For recording changes to the repository, use the `git-recording-changes-to-the-repository` skill instead.

## Key concepts

- If you want to check for new work in a submodule, you can go into the directory and run `git fetch` and `git merge` the upstream branch to update the local code.
- If you run `git submodule update --remote`, Git will go into your submodules and fetch and update for you.
- Git will by default try to update all of your submodules when you run `git submodule update--remote`.
- There is a special situation that can happen when pulling superproject updates: it could be that the upstream repository has changed the URL of the submodule in the `.gitmodules` file in one of the commits you pull.
- With no working branch tracking changes, that means even if you commit changes to the submodule, those changes will quite possibly be lost the next time you run `git submodule update`.
- If you haven’t committed your changes in your submodule and you run a `submodule update` that would cause issues, Git will fetch the changes but not overwrite unsaved work in your submodule directory.
- Using the `--recurse-submodules` flag of `git checkout` can also be useful when you work on several branches in the superproject, each having your submodule pointing at different commits.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git submodule update --remote --rebase`
  - `git clean -ffdx`
  - `git rm -r CryptoLibrary`
- **Note (from source):** Since the URL in the .gitmodules file is what other people will first try to clone/fetch from, make sure to use a URL that they can access if possible. For example, if you use a different URL to push to than others would to pull from, use the one that others have access to. You can overwrite this value locally with `gitconfig submodule.DbConnector.url PRIVATE_URL` for your own use. When applicable, a relative URL can be helpful.
- With no working branch tracking changes, that means even if you commit changes to the submodule, those changes will quite possibly be lost the next time you run `git submodule update`.
- If you haven’t committed your changes in your submodule and you run a `submodule update` that would cause issues, Git will fetch the changes but not overwrite unsaved work in your submodule directory.
- You can force it to switch with `checkout -f`, but be careful that you don’t have unsaved changes in there as they could be overwritten with that command.
- It’s important to note that submodules these days keep all their Git data in the top project’s `.git` directory, so unlike much older versions of Git, destroying a submodule directory won’t lose any commits or branches that you had.

## Procedures

### Starting with Submodules

**Goal:** Although `DbConnector` is a subdirectory in your working directory, Git sees it as a submodule and doesn’t track its contents when you’re not in that directory.

**Steps:**

1. In this example, we’ll add a library called “DbConnector”.
   ```bash
   git submodule add https://github.com/chaconinc/DbConnector
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'DbConnector'...
   remote: Counting objects: 11, done.
   remote: Compressing objects: 100% (10/10), done.
   remote: Total 11 (delta 0), reused 11 (delta 0)
   ```
2. Run:
   ```text
   Unpacking objects: 100% (11/11), done.
   Checking connectivity... done.
   ```
3. If you run `git status` at this point, you’ll notice a few things.
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes to be committed:
     (use "git reset HEAD <file>..." to unstage)
   ```
4. This is a configuration file that stores the mapping between the project’s URL and the local subdirectory you’ve pulled it into:
   ```ini
   [submodule "DbConnector"]
       path = DbConnector
       url = https://github.com/chaconinc/DbConnector
   ```
5. If you run `git diff` on that, you see something interesting:
   ```bash
   git diff --cached DbConnector
   ```
   Expected output (excerpt):
   ```text
   diff --git a/DbConnector b/DbConnector
   new file mode 160000
   index 0000000..c3f01dc
   --- /dev/null
   ```
6. Run:
   ```text
   +++ b/DbConnector
   @@ -0,0 +1 @@
   +Subproject commit c3f01dc8862123d317dd46284b05b6892c7b29bc
   ```

_3 more step(s) in references/procedures.md._

**Verify:** run `git diff --cached --submodule` - expect something like:
```text
diff --git a/.gitmodules b/.gitmodules
new file mode 100644
index 0000000..71fc376
--- /dev/null
+++ b/.gitmodules
@@ -0,0 +1,3 @@
```

### Cloning a Project with Submodules

**Goal:** To also initialize, fetch and checkout any nested submodules, you can use the foolproof `git submoduleupdate --init --recursive`.

**Steps:**

1. When you clone such a project, by default you get the directories that contain submodules, but none of the files within them yet:
   ```bash
   git clone https://github.com/chaconinc/MainProject
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'MainProject'...
   remote: Counting objects: 14, done.
   remote: Compressing objects: 100% (13/13), done.
   ```
2. Run:
   ```bash
   cd MainProject
   ls -la
   cd DbConnector/
   ls
   ```
   Expected output (excerpt):
   ```text
   total 16
   drwxr-xr-x   9 schacon  staff  306 Sep 17 15:21 .
   drwxr-xr-x   7 schacon  staff  238 Sep 17 15:21 ..
   drwxr-xr-x  13 schacon  staff  442 Sep 17 15:21 .git
   ```
3. `git submodule init` to initialize your local configuration file, and `git submodule update` to fetch all the data from that project and check out the appropriate commit listed in your superproject:
   ```bash
   git submodule init
   git submodule update
   ```
   Expected output (excerpt):
   ```text
   Submodule 'DbConnector' (https://github.com/chaconinc/DbConnector) registered for path
   'DbConnector'
   Cloning into 'DbConnector'...
   remote: Counting objects: 11, done.
   ```
4. If you pass `--recurse-submodules` to the `git clone` command, it will automatically initialize and update each submodule in the repository, including nested submodules if any of the submodules in the repository have submodules themselves.
   ```bash
   git clone --recurse-submodules https://github.com/chaconinc/MainProject
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'MainProject'...
   remote: Counting objects: 14, done.
   remote: Compressing objects: 100% (13/13), done.
   remote: Total 14 (delta 1), reused 13 (delta 0)
   ```
5. Run:
   ```text
   Checking connectivity... done.
   Submodule 'DbConnector' (https://github.com/chaconinc/DbConnector) registered for path
   'DbConnector'
   Cloning into 'DbConnector'...
   remote: Counting objects: 11, done.
   remote: Compressing objects: 100% (10/10), done.
   remote: Total 11 (delta 0), reused 11 (delta 0)
   Unpacking objects: 100% (11/11), done.
   Checking connectivity... done.
   Submodule path 'DbConnector': checked out 'c3f01dc8862123d317dd46284b05b6892c7b29bc'
   ```

### Working on a Project with Submodules

**Goal:** If you want to check for new work in a submodule, you can go into the directory and run `git fetch` and `git merge` the upstream branch to update the local code.

**Steps:**

1. If you want to check for new work in a submodule, you can go into the directory and run `git fetch` and `git merge` the upstream branch to update the local code.
   ```bash
   git fetch
   git merge origin/master
   ```
   Expected output (excerpt):
   ```text
   From https://github.com/chaconinc/DbConnector
      c3f01dc..d0354fc  master     -> origin/master
   Updating c3f01dc..d0354fc
   Fast-forward
   ```
2. If you don’t want to type `--submodule` every time you run `git diff`, you can set it as the default format by setting the `diff.submodule` config value to “log”.
   ```bash
   git config --global diff.submodule log
   git diff
   ```
   Expected output (excerpt):
   ```text
   Submodule DbConnector c3f01dc..d0354fc:
   ```
3. Run:
   ```text
     > more efficient db routine
     > better connection routine
   ```
4. If you run `git submodule update --remote`, Git will go into your submodules and fetch and update for you.
   ```bash
   git submodule update --remote DbConnector
   ```
   Expected output (excerpt):
   ```text
   remote: Counting objects: 4, done.
   remote: Compressing objects: 100% (2/2), done.
   remote: Total 4 (delta 2), reused 4 (delta 2)
   Unpacking objects: 100% (4/4), done.
   ```
5. Let’s set it in the `.gitmodules` file:
   ```bash
   git config -f .gitmodules submodule.DbConnector.branch stable
   git submodule update --remote
   ```
   Expected output (excerpt):
   ```text
   remote: Counting objects: 4, done.
   remote: Compressing objects: 100% (2/2), done.
   remote: Total 4 (delta 2), reused 4 (delta 2)
   Unpacking objects: 100% (4/4), done.
   ```
6. When we run `git status` at this point, Git will show us that we have “new commits” on the submodule.
   ```bash
   git status
   ```
   Expected output (excerpt):
   ```text
   On branch master
   Your branch is up-to-date with 'origin/master'.
   Changes not staged for commit:
   ```

_26 more step(s) in references/procedures.md._

**Verify:** run `git diff` - expect something like:
```text
diff --cc DbConnector
index eb41d76,c771610..0000000
--- a/DbConnector
+++ b/DbConnector
```

**If it fails:** You can go into the submodule directory and fix the conflict just as you normally would.

### Submodule Tips

**Goal:** There is a `foreach` submodule command to run some arbitrary command in each submodule.

**Steps:**

1. We can easily stash all the work in all our submodules.
   ```bash
   git submodule foreach 'git stash'
   ```
   Expected output (excerpt):
   ```text
   Entering 'CryptoLibrary'
   No local changes to save
   Entering 'DbConnector'
   Saved working directory and index state WIP on stable: 82d2ad3 Merge from
   ```
2. Then we can create a new branch and switch to it in all our submodules.
   ```bash
   git submodule foreach 'git checkout -b featureA'
   ```
   Expected output (excerpt):
   ```text
   Entering 'CryptoLibrary'
   Switched to a new branch 'featureA'
   Entering 'DbConnector'
   Switched to a new branch 'featureA'
   ```
3. One really useful thing you can do is produce a nice unified diff of what is changed in your main project and all your subprojects as well.
   ```bash
   git diff; git submodule foreach 'git diff'
   ```
   Expected output (excerpt):
   ```text
   Submodule DbConnector contains modified content
   diff --git a/src/main.c b/src/main.c
   index 210f1ae..1f0acdc 100644
   --- a/src/main.c
   ```
4. Run:
   ```text
   +       return url_decode_mem(url, strlen(url));
   +}
   +
    char *url_decode_parameter_name(const char **query)
    {
           struct strbuf out = STRBUF_INIT;
   ```
5. You may want to set up some aliases for some of these commands as they can be quite long and you can’t set configuration options for most of them to make them defaults.
   ```bash
   git config alias.sdiff '!'"git diff && git submodule foreach 'git diff'"
   git config alias.spush 'push --recurse-submodules=on-demand'
   git config alias.supdate 'submodule update --remote --merge'
   ```

**Verify:** run `git diff; git submodule foreach 'git diff'` - expect something like:
```text
Submodule DbConnector contains modified content
diff --git a/src/main.c b/src/main.c
index 210f1ae..1f0acdc 100644
--- a/src/main.c
+++ b/src/main.c
@@ -245,6 +245,8 @@ static int handle_alias(int *argcp, const char ***argv)
```

### Issues with Submodules

**Goal:** For older Git versions that do not have the `--recurse-submodules` flag, after the checkout you can use `git submodule update --init --recursive` to put the submodules in the right state.

**Steps:**

1. If you create a new branch, add a submodule there, and then switch back to a branch without that submodule, you still have the submodule directory as an untracked directory:
   ```bash
   git --version
   git checkout -b add-crypto
   git submodule add https://github.com/chaconinc/CryptoLibrary
   git commit -am 'Add crypto library'
   ```
   Expected output (excerpt):
   ```text
   git version 2.12.2
   Switched to a new branch 'add-crypto'
   Cloning into 'CryptoLibrary'...
   ...
   ```
2. Run:
   ```bash
   git checkout master
   git status
   ```
   Expected output (excerpt):
   ```text
   warning: unable to rmdir CryptoLibrary: Directory not empty
   Switched to branch 'master'
   Your branch is up-to-date with 'origin/master'.
   On branch master
   ```
3. If you do remove it and then switch back to the branch that has that submodule, you will need to run `submodule update --init` to repopulate it.
   ```bash
   git clean -ffdx
   git checkout add-crypto
   ls CryptoLibrary/
   git submodule update --init
   ls CryptoLibrary/
   ```
   Expected output (excerpt):
   ```text
   Removing CryptoLibrary/
   Switched to branch 'add-crypto'
   Submodule path 'CryptoLibrary': checked out 'b8dda6aa182ea4464f3f3264b11e0268545172af'
   Makefile    includes    scripts     src
   ```
4. Newer Git versions (Git >= 2.13) simplify all this by adding the `--recurse-submodules` flag to the `gitcheckout` command, which takes care of placing the submodules in the right state for the branch we are switching to.
   ```bash
   git --version
   git checkout -b add-crypto
   git submodule add https://github.com/chaconinc/CryptoLibrary
   ```
   Expected output (excerpt):
   ```text
   git version 2.13.3
   Switched to a new branch 'add-crypto'
   ```
5. Run:
   ```bash
   git commit -am 'Add crypto library'
   git checkout --recurse-submodules master
   git status
   ```
   Expected output (excerpt):
   ```text
   [add-crypto 4445836] Add crypto library
    2 files changed, 4 insertions(+)
    create mode 160000 CryptoLibrary
   Switched to branch 'master'
   ```
6. If you delete the subdirectory and then run `submodule add`, Git yells at you:
   ```bash
   rm -Rf CryptoLibrary/
   git submodule add https://github.com/chaconinc/CryptoLibrary
   ```
   Expected output (excerpt):
   ```text
   'CryptoLibrary' already exists in the index
   ```

_3 more step(s) in references/procedures.md._

**If it fails:** Then, when you switch back, you get an empty `CryptoLibrary` directory for some reason and `gitsubmodule update` may not fix it either.

More procedures in [references/procedures.md](references/procedures.md):

- Starting with Submodules
- Working on a Project with Submodules
- Issues with Submodules

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git submodule` | To also initialize, fetch and checkout any nested submodules, you can use the foolproof `git submoduleupdate --init --recursive`. | `git submodule init` |
| `git status` | The other listing in the `git status` output is the project folder entry. | `git status` |
| `git commit -am` | When you commit, you see something like this | `git commit -am 'Unicode support'` |
| `git diff` | If you run `git diff` you can get the | `git diff` |
| `git merge` | If you want to check for new work in a submodule, you can go into the directory and run `git fetch` and `git merge` the upstream branch to update the local code. | `git merge 9fd905e` |
| `git submodule --remote` | If you run `git submodule update --remote`, Git will go into your submodules and fetch and update for you. | `git submodule update --remote` |
| `git checkout` | You may need to go into your submodule directory and run a `git checkout .` to get all your files back. | `git checkout stable` |
| `git add` | Git addresses this issue using submodules. | `git add src/main.c` |
| `git config` | You can make this behavior the default by doing `git config push.recurseSubmodules on-demand`. | `git config status.submodulesummary 1` |
| `git pull` | If you want to automate this process, you can add the `--recurse-submodules` flag to the `git pull` command (since Git 2.14). | `git pull` |
| `git submodule --init --recursive` | To finalize the update, you need to run `git submodule update` | `git submodule update --init --recursive` |
| `git submodule --remote --merge` | Here we’ll see that there was a change on the server for this submodule and it gets merged in. | `git submodule update --remote --merge` |
| `git push --recurse-submodules` | The “check” option will make `push` simply fail if any of the committed submodule changes haven’t been pushed. | `git push --recurse-submodules=check` |
| `git --version` | If you create a new branch, add a submodule there, and then switch back to a branch without that submodule, you still have the submodule directory as an untracked directory | `git --version` |
| `git checkout -b` | If you create a new branch, add a submodule there, and then switch back to a branch without that submodule, you still have the submodule directory as an untracked directory | `git checkout -b add-crypto` |
| `git diff --cached` | If you run `git diff` on that, you see something interesting | `git diff --cached DbConnector` |
| `git diff --cached --submodule` | If you want a little nicer diff output, you can pass the `--submodule` option to `git diff`. | `git diff --cached --submodule` |
| `git push` | The `git push` command takes the `--recurse-submodules` argument which can be set to either “check” or “on-demand”. | `git push origin master` |
| `git clone` | As noted above, this will also make Git recurse into submodules for every command that has a `--recurse-submodules` option (except `git clone`). | `git clone https://github.com/chaconinc/MainProject` |
| `git clone --recurse-submodules` | If you pass `--recurse-submodules` to the `git clone` command, it will automatically initialize and update each submodule in the repository, including nested submodules if any of the submodules in the repository have submodules themselves. | `git clone --recurse-submodules https://github.com/chaconinc/MainProject` |

## Decision guide

- Instead of writing your own Atom-generating code, you decide to use a library.
- There is an easier way to do this as well, if you prefer to not manually fetch and merge in the subdirectory.
- If one of the commits is a direct ancestor of the other (a fast-forward merge), then Git will simply choose the latter for the merge, so that works fine.
- If we go into our submodule directory, it should already be on `eb41d76` as the merge would not have touched it.
- If you’ve been tracking files in your project and you want to move them out into a submodule, you must be careful or Git will get angry at you.

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

## Source

"Pro Git", pages 304-324. Sections: Submodules; Submodules > Starting with Submodules; Submodules > Cloning a Project with Submodules; Submodules > Working on a Project with Submodules; Submodules > Submodule Tips; Submodules > Issues with Submodules.
