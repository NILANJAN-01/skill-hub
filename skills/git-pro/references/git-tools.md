# Git Tools

_Source: Pro Git, pages 224-341_

## Topics covered

- Revision Selection
- Interactive Staging
- Stashing and Cleaning
- Signing Your Work
- Searching
- Rewriting History
- Reset Demystified
- Advanced Merging
- Rerere
- Debugging with Git
- Submodules
- Bundling
- Replace
- Credential Storage
- Summary

**Key terms:** submodule, hello, dbconnector, commit, merge, stash, file, head, bundle, commits

## Key points

- For example, to examine a specific commit where you know you added certain functionality, you might first run the git log command to locate the commit: `git log`.
- Branch References One straightforward way to refer to a particular commit is if it’s the commit at the tip of a branch; in that case, you can simply use the branch name in any Git command that expects a reference to a commit.
- You can see your reflog by using git reflog: `git reflog`.
- To see reflog information formatted like the git log output, you can run git log -g: `git log -g master`.
- If you run a git push and your current branch is tracking origin/master, the commits listed by git log origin/master..HEAD are the commits that will be transferred to the server.
- If you run git add with the -i or --interactive option, Git enters an interactive shell mode, displaying something like this: `git add -i`.
- To push a new stash onto your stack, run git stash or git stash push: `git stash`.
- In Git 1.8.3 and later, git merge and git pull can be told to inspect and reject when merging a commit that does not carry a trusted GPG signature with the --verify-signatures command.
- We’ve also been referring to this concept as Git’s “Staging Area” as this is what Git looks at when you run git commit.
- You then replace some of those files with new versions of them, and git commit converts that into the tree for a new commit. `git ls-files -s`.
- When you run git commit, Git creates a new commit and moves the branch that HEAD points to up to it.
- You could now update the index and run git commit again to accomplish what git commit --amend would have done (see Changing the Last Commit).
- You undid your last commit, the git add and git commit commands, and all the work you did in your working directory.
- Git repository You can run git reset --soft HEAD~2 to move the HEAD branch back to an older commit (the most recent commit you want to keep): Figure 152.
- Git will output this format if you run git show on a merge commit, or if you add a --cc option to a git log -p (which by default only shows patches for non-merge commits). `git log --cc -p -1`.
- We can do that in Git with git read-tree.
- However, git rerere will also tell you what it has recorded the pre-merge state for with git rerere status: `git rerere status`.
- You run your test again and find that this commit is broken, so you tell Git that with git bisect bad: `git bisect bad`.
- You must run two commands from the main project: git submodule init to initialize your local configuration file, and git submodule update to fetch all the data from that project and check out the appropriate commit listed in your superproject: `git submodule init`.
- If you already cloned the project and forgot --recurse-submodules, you can combine the git submodule init and git submodule update steps by running git submodule update --init .
- If you want to check for new work in a submodule, you can go into the directory and run git fetch and git merge the upstream branch to update the local code. `git fetch`.
- If you run git submodule update --remote, Git will go into your submodules and fetch and update for you. `git submodule update --remote DbConnector`.
- When we run git status at this point, Git will show us that we have “new commits” on the submodule. `git status`.
- We covered setting up Git aliases in Git Aliases, but here is an example of what you may want to set up if you plan on working with submodules in Git a lot. `git config alias.sdiff '!'"git diff && git submodule foreach 'git diff'"`.
- Newer Git versions (Git >= 2.13) simplify all this by adding the --recurse-submodules flag to the git checkout command, which takes care of placing the submodules in the right state for the branch we are switching to. `git --version`.

## Commands / code

```
$ git log
$ git show 1c002dd4b536e7479fe34593e72e6c6c1819e53b
$ git show 1c002dd4b536e7479f
$ git show 1c002d
$ git log --abbrev-commit --pretty=oneline
$ git show ca82a6dff817ec66f44342007202690a93763949
$ git show topic1
$ git rev-parse topic1
$ git reflog
$ git show HEAD@{5}
$ git show master@{yesterday}
$ git log -g master
$ git show HEAD@{0}     # will NOT work
$ git show HEAD@`{0`}   # OK
$ git log --pretty=format:'%h %s' --graph
$ git show HEAD^
$ git show HEAD^     # will NOT work on Windows
$ git show HEAD^^    # OK
$ git show d921970^
$ git show d921970^2
$ git show HEAD~3
$ git log master..experiment
$ git log experiment..master
$ git log origin/master..HEAD
$ git log refA..refB
$ git log refB --not refA
$ git log refA refB ^refC
$ git log refA refB --not refC
$ git log --left-right master...experiment
> D
> C
$ git add -i
<p id="out">...</p>
<script type="text/javascript">
def log(treeish = 'master')
def blame(path)
$ git status
$ git stash
$ git stash list
$ git stash apply
```

## Rules, tips and warnings

- Single Revisions You can obviously refer to any single commit by its full, 40-character SHA-1 hash, but there are more human-friendly ways to refer to commits as well.
- You can inspect that commit with any of the following variations of git show (assuming the shorter versions are unambiguous): `git show 1c002dd4b536e7479fe34593e72e6c6c1819e53b`.
- If you try to check out that object again at some point, you’ll always get the data of the first object.
- However, you should be aware of how ridiculously unlikely this scenario is.
- Branch References One straightforward way to refer to a particular commit is if it’s the commit at the tip of a branch; in that case, you can simply use the branch name in any Git command that expects a reference to a commit.
- For instance, if you want to examine the last commit object on a branch, the following commands are equivalent, assuming that the topic1 branch points to commit ca82a6d…: `git show ca82a6dff817ec66f44342007202690a93763949`.
- If you want to see which specific SHA-1 a branch points to, or if you want to see what any of these examples boils down to in terms of SHA-1s, you can use a Git plumbing tool called rev-parse.
- You can see Git Internals for more information about plumbing tools; basically, rev-parse exists for lower-level operations and isn’t designed to be used in day-to-day operations.
- Here you can run rev-parse on your branch. `git rev-parse topic1`.
- You can see your reflog by using git reflog: `git reflog`.
- Every time your branch tip is updated for any reason, Git stores that information for you in this temporary history.
- You can use your reflog data to refer to older commits as well.
