# Distributed Git

_Source: Pro Git, pages 132-171_

## Topics covered

- Distributed Workflows
- Contributing to a Project
- Maintaining a Project
- Summary

**Key terms:** jessica, patch, featurea, branch, john, topic, simplegit, maintainer, master, githost

## Key points

- Distributed Git Now that you have a remote Git repository set up as a focal point for all the developers to share their code, and you’re familiar with basic Git commands in a local workflow, you’ll look at how to utilize some of the distributed workflows that Git affords you.
- As a first step, John fetches Jessica’s work (this only fetches Jessica’s upstream work, it does not yet merge it into John’s work): `git fetch origin`.
- Now John can merge Jessica’s work that he fetched into his own local work: `git merge origin/master`.
- Now, Jessica can merge her topic work into her master branch, merge John’s work ( origin/master) into her master branch, and then push back to the server again.
- First (having committed all of the work on her issue54 topic branch), Jessica switches back to her master branch in preparation for integrating all this work: `git checkout master`.
- Jessica now completes the local merging process by merging John’s earlier fetched work that is sitting in the origin/master branch: `git merge origin/master`.
- Now origin/master is reachable from Jessica’s master branch, so she should be able to successfully push (assuming John hasn’t pushed even more changes in the meantime): `git push origin master`.
- You work for a while (generally in a topic branch), and merge that work into your master branch when it’s ready to be integrated.
- Jessica doesn’t have push access to the master branch — only the integrators do — so she has to push to another branch in order to collaborate with John: `git push -u origin featureA`.
- Assuming Jessica is still on her checked-out featureB branch, she can now merge Josie’s work into that branch with git merge: `git merge origin/featureBee`.
- The git request-pull command takes the base branch into which you want your topic branch pulled and the Git repository URL you want them to pull from, and produces a summary of all the changes you’re asking to be pulled.
- For example, if you want to submit a second topic of work to the project, don’t continue working on the topic branch you just pushed up — start over from the main repository’s master branch: `git checkout -b featureB origin/master`.
- You start a new branch based off the current origin/master branch, squash the featureB changes there, resolve any conflicts, make the implementation change, and then push that as a new branch: `git checkout -b featureBv2 origin/master`.
- As you’ll remember, you can create the branch based off your master branch like this: `git branch sc/ruby_client master`.
- You can also use git apply to see if a patch applies cleanly before you try actually applying it — you can run git apply --check with the patch: `git apply --check 0001-see-if-this-helps-the-gem.patch`.
- For instance, if Jessica sends you an email saying that she has a great new feature in the ruby-client branch of her repository, you can test it by adding the remote and checking out that branch locally: `git remote add jessica https://github.com/jessica/myproject.git`.
- This happens because Git directly compares the snapshots of the last commit of the topic branch you’re on and the snapshot of the last commit on the master branch.
- What you really want to see are the changes added to the topic branch — the work you’ll introduce if you merge this branch with master.
- You do that by having Git compare the last commit on your topic branch with the first common ancestor it has with the master branch.
- In the context of the git diff command, you can put three periods after another branch to do a diff between the last commit of the branch you’re on and its common ancestor with another branch: `git diff master...contrib`.
- When you have work in a topic branch that you think you’ve completed, or work that someone else has contributed and you’ve verified, you merge it into your master branch, delete that just-merged topic branch, and repeat.
- Each time you have a new topic branch to merge in (Before a topic branch merge), you merge it into develop (After a topic branch merge); then, when you tag a release, you fast-forward master to wherever the nowstable develop branch is (After a project release).
- When you have work in a topic branch and have determined that you want to integrate it, you move to that branch and run the rebase command to rebuild the changes on top of your current master (or develop, and so on) branch.
- The command to do this is git archive: `git archive master --prefix='project/' | gzip > `git describe master`.tar.gz`.
- You can also create a zip archive in much the same way, but by passing the --format=zip option to git archive: `git archive master --prefix='project/' --format=zip > `git describe master`.zip`.

## Commands / code

```
$ git clone john@githost:simplegit.git
$ cd simplegit/
$ vim lib/simplegit.rb
$ git commit -am 'Remove invalid default value'
$ git clone jessica@githost:simplegit.git
$ vim TODO
$ git commit -am 'Add reset task'
$ git push origin master
$ git fetch origin
$ git merge origin/master
$ git log --no-merges issue54..origin/master
$ git checkout master
$ git merge issue54
$ git checkout -b featureA
$ git commit -am 'Add limit to log function'
$ git push -u origin featureA
$ git checkout -b featureB origin/master
$ git commit -am 'Make ls-tree function recursive'
$ git commit -am 'Add ls-files'
$ git merge origin/featureBee
$ git push -u origin featureB:featureBee
$ git log featureA..origin/featureA
$ git checkout featureA
$ git merge origin/featureA
$ git commit -am 'Add small tweak to merged content'
$ git push
$ git clone <url>
$ cd project
$ git commit
$ git remote add myfork <url>
$ git push -u myfork featureA
$ git request-pull origin/master myfork
$ git push myfork featureB
$ git rebase origin/master
$ git push -f myfork featureA
$ git checkout -b featureBv2 origin/master
$ git merge --squash featureB
$ git push myfork featureBv2
$ git checkout -b topicA
$ git format-patch -M origin/master
```

## Rules, tips and warnings

- The second developer must merge in the first one’s work before pushing changes up, so as not to overwrite the first developer’s changes.
- If you are already comfortable with a centralized workflow in your company or team, you can easily continue using that workflow with Git.
- Then, you can send a request to the maintainer of the main project to pull in your changes.
- One of the main advantages of this approach is that you can continue to work, and the maintainer of the main repository can pull in your changes at any time.
- There’s also a section comparing high and low integration frequencies. https://martinfowler.com/articles/branching-patterns.html Workflows Summary These are some commonly used workflows that are possible with a distributed system like Git, but you can see that many variations are possible to suit your particular real-world workflow.
- Because Git is very flexible, people can and do work together in many ways, and it’s problematic to describe how you should contribute — every project is a bit different.
- This is important because with more and more developers, you run into more issues with making sure your code applies cleanly or can be easily merged.
- Commit Guidelines Before we start looking at the specific use cases, here’s a quick note about commit messages.
- The Git project provides a document that lays out a number of good tips for creating commits from which to submit patches — you can read it in the Git source code in the Documentation/SubmittingPatches file.
- First, your submissions should not contain any whitespace errors.
- Output of git diff --check If you run that command before committing, you can tell if you’re about to commit whitespace issues that may annoy other developers.
- If you can, try to make your changes digestible — don’t code for a whole weekend on five different issues and then submit them all as one massive commit on Monday.
