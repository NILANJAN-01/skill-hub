# Git and Other Systems

_Source: Pro Git, pages 373-419_

## Topics covered

- Git as a Client
- Migrating to Git
- Summary

**Key terms:** perforce, svn, depot, trunk, dir, mercurial, git-p4, fusion, subversion, test-svn

## Key points

- One of Git’s great features is a bidirectional bridge to Subversion called git svn.
- This tool allows you to use Git as a valid client to a Subversion server, so you can use all the local features of Git and then push to a Subversion server as if you were using Subversion locally.
- The Subversion bridge is the gateway drug to the DVCS world. git svn The base command in Git for all the Subversion bridging commands is git svn.
- It’s important to note that when you’re using git svn, you’re interacting with Subversion, which is a system that works very differently from Git.
- You’ll start with the git svn clone command, which imports an entire Subversion repository into a local Git repository.
- At this point, you should have a valid Git repository that has imported your branches and tags: `git branch -a`.
- Git doesn’t do this when it clones from a Git server; here’s what a repository with tags looks like after a fresh clone: `git show-ref`.
- To push to a Subversion server, you run the git svn dcommit command: `git svn dcommit`.
- In git svn, it looks like this: `git svn dcommit`.
- You can run git svn fetch to grab the new data, but git svn rebase does the fetch and then updates your local commits. `git svn rebase`.
- Creating a New SVN Branch To create a new branch in Subversion, you run git svn branch [new-branch]: `git svn branch opera`.
- SVN Style History If you’re used to Subversion and want to see your history in SVN output style, you can run git svn log to view your commit history in SVN formatting: `git svn log`.
- The second command is git svn show-ignore, which prints to stdout the lines you need to put in a .gitignore file so you can redirect the output into your project exclude file: `git svn show-ignore > .git/info/exclude`.
- On the Git side: `git checkout -b featureA`.
- Git Fusion Perforce provides a product called Git Fusion (available at https://www.perforce.com/manuals/gitfusion/), which synchronizes a Perforce server with Git repositories on the server side.
- When converting from a Perforce changeset to a Git commit, Git Fusion’s default behavior is to look up the Perforce user, and use the email address and full name stored there for the author/committer field in Git.
- If you want to freely mix the use of Perforce and Git as clients for source control, and you can convince the server administrator to install it, Git Fusion makes using Git a first-class versioncontrol client for a Perforce server.
- Subversion If you read the previous section about using git svn, you can easily use those instructions to git svn clone a repository; then, stop using the Subversion server, push to a new Git server, and start using that.
- To move the tags to be proper Git tags, run: `for t in $(git for-each-ref --format='%(refname:short)' refs/remotes/tags); do git`.
- Here is an example of adding your server as a remote: `git remote add origin git@my-git-server:myrepository.git`.
- Mercurial Since Mercurial and Git have fairly similar models for representing versions, and since Git is a bit more flexible, converting a repository from Mercurial to Git is fairly straightforward, using a tool called "hg-fast-export", which you’ll need a copy of: `git clone https://github.com/frej/fast-export.git`.
- Now you’re ready to push the repository up to its new server-side home: `git remote add origin git@my-git-server:myrepository.git`.
- As we discussed above, there are two ways to let Git and Perforce talk to each other: git-p4 and Perforce Git Fusion.
- Git Fusion leaves you with what looks like a native Git repository, which is then ready to push to a native Git host if you desire.
- Now, you can run git log to see your new history: `git log -2`.

## Commands / code

```
$ mkdir /tmp/test-svn
$ svnadmin create /tmp/test-svn
$ cat /tmp/test-svn/hooks/pre-revprop-change
exit 0;
$ chmod +x /tmp/test-svn/hooks/pre-revprop-change
$ svnsync init file:///tmp/test-svn \
$ svnsync sync file:///tmp/test-svn
$ git svn clone file:///tmp/test-svn -T trunk -b branches -t tags
$ git svn clone file:///tmp/test-svn -s
$ git branch -a
$ git show-ref
$ git commit -am 'Adding git-svn instructions to the README'
$ git svn dcommit
$ git log -1
$ git svn rebase
$ git svn branch opera
$ git branch opera remotes/origin/opera
$ git svn log
$ git svn blame README.txt
$ git svn info
$ git svn show-ignore > .git/info/exclude
$ curl -o ~/bin/git-remote-hg \
$ chmod +x ~/bin/git-remote-hg
$ pip install mercurial
$ hg clone http://selenic.com/repo/hello /tmp/hello
$ git clone hg::/tmp/hello /tmp/hello-git
$ cd /tmp/hello-git
$ git log --oneline --graph --decorate
$ tree .git/refs
$ cat notes/hg
$ git cat-file -p d4c10386...
$ git ls-tree 1781c96...
$ git cat-file -p ac9117f
$ cp .hgignore .git/info/exclude
$ git fetch
$ git log --oneline --graph --decorate --all
$ git merge origin/master
$ git push
$ hg log -G --style compact
$ hg log -l 1
```

## Rules, tips and warnings

- Usually, you can’t immediately switch every project you come in contact with to Git.
- This tool allows you to use Git as a valid client to a Subversion server, so you can use all the local features of Git and then push to a Subversion server as if you were using Subversion locally.
- This means you can do local branching and merging, use the staging area, use rebasing and cherry-picking, and so on, while your collaborators continue to work in their dark and ancient ways.
- It’s important to note that when you’re using git svn, you’re interacting with Subversion, which is a system that works very differently from Git.
- Although you can do local branching and merging, it’s generally best to keep your history as linear as possible by rebasing your work, and avoiding doing things like simultaneously interacting with a Git remote repository.
- If you’re working with a team, and some are using SVN and others are using Git, make sure everyone is using the SVN server to collaborate – doing so will make your life easier.
- If you want to copy these examples, you’ll have to make a writeable copy of an SVN test repository.
- In order to do that easily, you can use a tool called svnsync that comes with Subversion.
- Then, enable all users to change revprops – the easy way is to add a pre-revprop-change script that always exits 0: `cat /tmp/test-svn/hooks/pre-revprop-change`.
- You can now sync this project to your local machine by calling svnsync init with the to and from repositories. `svnsync init file:///tmp/test-svn \`.
- You can then clone the code by running: `svnsync sync file:///tmp/test-svn`.
- Getting Started Now that you have a Subversion repository to which you have write access, you can go through a typical workflow.
