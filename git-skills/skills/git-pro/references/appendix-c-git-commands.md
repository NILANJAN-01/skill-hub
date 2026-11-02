# Appendix C: Git Commands

_Source: Pro Git, pages 484-498_

## Topics covered

- Setup and Config
- Getting and Creating Projects
- Basic Snapshotting
- Branching and Merging
- Sharing and Updating Projects
- Inspection and Comparison
- Debugging
- Patching
- Email
- External Systems
- Administration
- Plumbing Commands

**Key terms:** command, git, editor, merge, core, commit, global, branch, submodule, throughout

## Key points

- For example, you can type in git commit --a , which acts as if you typed git commit --amend .
- It creates a new directory, goes into it and runs git init to make it an empty Git repository, adds a remote ( git remote add ) to the URL that you pass it (by default named origin), runs a git fetch from that remote repository and then checks out the latest commit into your working directory with git checkout.
- Finally, we take a look at what the git commit command does in the background and how it’s actually implemented in Commit Objects. git reset The git reset command is primarily used to undo things, as you can possibly tell by the verb.
- We use git reset --hard to abort a merge in Aborting a Merge , where we also use git merge --abort, which is a bit of a wrapper for the git reset command. git rm The git rm command is used to remove files from the staging area and working directory for Git.
- This can be useful for scripting purposes. git mv The git mv command is a thin convenience command to move a file and then run git add on the new file and git rm on the old file.
- We set up highly custom refspecs in order to make git fetch do something a little different than the default in The Refspec. git pull The git pull command is basically a combination of the git fetch and git merge commands, where Git will fetch from the remote you specify and then immediately try to merge it into the branch you’re on.
- Inspection and Comparison git show The git show command can show a Git object in a simple and human readable way.
- One of the more interesting things we do with git show is in Manual File Re-merging to extract specific file contents of various stages during a merge conflict. git shortlog The git shortlog command is used to summarize the output of git log.
- Git has a number of tools built into it that help make this process easier, from generating patches you can easily email to applying those patches from an email box. git apply The git apply command applies a patch created with the git diff or even GNU diff command.
- We go through an example of contributing to a project using the git format-patch tool in Public Project over Email. git imap-send The git imap-send command uploads a mailbox generated with git format-patch into an IMAP drafts folder.
- We go through an example of contributing to a project by sending patches with the git imap-send tool in Public Project over Email. git send-email The git send-email command is used to send patches that are generated with git format-patch over email.
- This command is covered in depth in Git and Subversion. git fast-import For other version control systems or importing from nearly any format, you can use git fastimport to quickly map the other format to something Git can easily record.

## Rules, tips and warnings

- For example, you can type in git commit --a , which acts as if you typed git commit --amend .
- For a lot of these things, you can tell Git to default to doing them a different way, or set your preferences.
- There are several files this command will read from and write to so you can set values globally or down to specific repositories.
- One is to copy it from an existing repository on the network or elsewhere and the other is to create a new one in an existing directory. git init To take a directory and turn it into a new Git repository so you can start version controlling it, you can simply run git init.
- We talk briefly about how you can change the default branch name from “master” in Remote Branches.
- Finally, we emulate it at a low level in Tree Objects, so you can get an idea of what it’s doing behind the scenes. git status The git status command will show you the different states of files in your working directory and staging area.
- Finally, we take a look at what the git commit command does in the background and how it’s actually implemented in Commit Objects. git reset The git reset command is primarily used to undo things, as you can possibly tell by the verb.
- This final option makes it possible for this command to lose your work if used incorrectly, so make sure you understand it before using it.
- Finally, we very quickly mention that you can use the --verify-signatures option to it in order to verify that commits you are pulling have been GPG signed in Signing Commits. git push The git push command is used to communicate with another repository, calculate what your local database has that the remote one does not, and then pushes the difference into the other repository.
- In Other Client Hooks we talk briefly about the pre-push hook, which is a script we can setup to run before a push completes to verify that it should be allowed to push.
- You can have several of these and the git remote command is used to add, change and delete them.
- Git has a number of tools built into it that help make this process easier, from generating patches you can easily email to applying those patches from an email box. git apply The git apply command applies a patch created with the git diff or even GNU diff command.
