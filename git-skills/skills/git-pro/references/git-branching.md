# Git Branching

_Source: Pro Git, pages 69-110_

## Topics covered

- Branches in a Nutshell
- Basic Branching and Merging
- Branch Management
- Branching Workflows
- Remote Branches
- Rebasing
- Summary

**Key terms:** branch, serverfix, iss53, hotfix, merge, master, commit, branches, teamone, origin

## Key points

- Every time you commit, the master branch pointer moves forward automatically.  The “master” branch in Git is not a special branch.
- A branch and its commit history Creating a New Branch What happens when you create a new branch?
- You do this with the git branch command: `git branch testing`.
- The git branch command only created a new branch — it didn’t switch to that branch.
- The HEAD branch moves forward when a commit is made This is interesting, because now your testing branch has moved forward, but your master branch still points to the commit you were on when you ran git checkout to switch branches.
- From Git version 2.23 onwards you can use git switch instead of git checkout to: • Switch to an existing branch: git switch testing-branch. • Create a new branch and switch to it: git switch -c new-branch .
- You can delete it with the -d option to git branch: `git branch -d hotfix`.
- If you need to pull it in, you can merge your master branch into your iss53 branch by running git merge master, or you can wait to integrate those changes until you decide to pull the iss53 branch back into master later.
- To see the last commit on each branch, you can run git branch -v: `git branch -v`.
- To see which branches are already merged into the branch you’re on, you can run git branch --merged: `git branch --merged`.
- To see all the branches that contain work you haven’t yet merged in, you can run git branch --no -merged: `git branch --no-merged`.
- Rename the branch locally with the git branch --move command: `git branch --move bad-branch-name corrected-branch-name`.
- After you’ve done all these tasks, and are certain the main branch performs just as the master branch, you can delete the master branch: `git push origin --delete master`.
- If you were working on an issue with a partner and they pushed up an iss53 branch, you might have your own local iss53 branch, but the branch on the server would be represented by the remote-tracking branch origin/iss53.
- Git also gives you your own local master branch starting at the same place as origin’s master branch, so you have something to work from.  “origin” is not special Just like the branch name “master” does not have any special meaning in Git, neither does “origin”.
- Tracking Branches Checking out a local branch from a remote-tracking branch automatically creates what is called a “tracking branch” (and the branch it tracks is called an “upstream branch”).
- Switched to a new branch 'serverfix' To set up a local branch with a different name than the remote branch, you can easily use the first version with a different local branch name: `git checkout -b sf origin/serverfix`.
- If you already have a local branch and want to set it to a remote branch you just pulled down, or want to change the upstream branch you’re tracking, you can use the -u or --set-upstream-to option to git branch to explicitly set it at any time. `git branch -u origin/serverfix`.
- You could do that like this: `git fetch --all; git branch -vv`.
- If you have a tracking branch set up as demonstrated in the last section, either by explicitly setting it or by having it created for you by the clone or checkout commands, git pull will look up what server and branch your current branch is tracking, fetch from that server and then try to merge in that remote branch.
- Rebasing a topic branch off another topic branch Now you can fast-forward your master branch (see Fast-forwarding your master branch to include the client branch changes): `git checkout master`.
- You can rebase the server branch onto the master branch without having to check it out first by running git rebase <basebranch> <topicbranch> — which checks out the topic branch (in this case, server) for you and replays it onto the base branch (master): `git rebase master server`.
- Rebasing your server branch on top of your master branch Then, you can fast-forward the base branch (master): `git checkout master`.

## Commands / code

```
$ git add README test.rb LICENSE
$ git commit -m 'Initial commit'
$ git branch testing
$ git log --oneline --decorate
$ git checkout testing
$ vim test.rb
$ git commit -a -m 'Make a change'
$ git checkout master
$ git commit -a -m 'Make other changes'
$ git log --oneline --decorate --graph --all
<newbranchname>.
$ git checkout -b iss53
$ git branch iss53
$ git checkout iss53
$ vim index.html
$ git commit -a -m 'Create new footer [issue 53]'
$ git checkout -b hotfix
$ git commit -a -m 'Fix broken email address'
$ git merge hotfix
$ git branch -d hotfix
$ git commit -a -m 'Finish the new footer [issue 53]'
$ git merge iss53
$ git branch -d iss53
$ git status
<div id="footer">contact : email.support@github.com</div>
<div id="footer">
</div>
$ git mergetool
$ git branch
$ git branch -v
$ git branch --merged
$ git branch --no-merged
$ git branch -d testing
$ git branch --no-merged master
$ git branch --move bad-branch-name corrected-branch-name
$ git push --set-upstream origin corrected-branch-name
$ git branch --all
$ git push origin --delete bad-branch-name
$ git branch --move master main
$ git push --set-upstream origin main
```

## Rules, tips and warnings

- Note that this is a lot different than the concept of HEAD in other VCSs you may be used to, such as Subversion or CVS.
- HEAD pointing to a branch You can easily see this by running a simple git log command that shows you where the branch pointers are pointing.
- You can see the master and testing branches that are right there next to the f30ab commit.
- It essentially rewinds the work you’ve done in your testing branch so you can go in a different direction.  Switching branches changes files in your working directory It’s important to note that when you switch branches in Git, files in your working directory will change.
- Both of those changes are isolated in separate branches: you can switch back and forth between the branches and merge them together when you’re ready.
- Divergent history You can also see this easily with the git log command.
- This can take several seconds or even minutes, depending on the size of the project, whereas in Git the process is always instantaneous.
- Let’s see why you should do so.  Creating a new branch and switching to it at the same time It’s typical to create a new branch and want to switch to that new branch at the same time — this can be done in one operation with git checkout -b
- From Git version 2.23 onwards you can use git switch instead of git checkout to: • Switch to an existing branch: git switch testing-branch. • Create a new branch and switch to it: git switch -c new-branch .
- The -c flag stands for create, you can also use the full flag: --create. • Return to your previously checked out branch: git switch -.
- To create a new branch and switch to it at the same time, you can run the git checkout command with the -b switch: `git checkout -b iss53`.
- With Git, you don’t have to deploy your fix along with the iss53 changes you’ve made, and you don’t have to put a lot of effort into reverting those changes before you can work on applying your fix to what is in production.
