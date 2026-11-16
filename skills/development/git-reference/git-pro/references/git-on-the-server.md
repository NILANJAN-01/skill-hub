# Git on the Server

_Source: Pro Git, pages 111-131_

## Topics covered

- The Protocols
- Getting Git on a Server
- Generating Your SSH Public Key
- Setting Up the Server
- Git Daemon
- Smart HTTP
- GitWeb
- GitLab
- Third Party Hosted Options
- Summary

**Key terms:** ssh, srv, server, gitlab, cgi, bare, access, repository, gitweb, user

## Key points

- Git on the Server At this point, you should be able to do most of the day-to-day tasks for which you’ll be using Git.
- However, in order to do any collaboration in Git, you’ll need to have a remote Git repository.
- A remote repository is generally a bare repository — a Git repository that has no working directory.
- For example, to clone a local repository, you can run something like this: `git clone /srv/git/project.git`.
- To add a local repository to an existing Git project, you can run something like this: `git remote add local_proj /srv/git/project.git`.
- To clone a Git repository over SSH, you can specify an ssh:// URL like this: `git clone ssh://[user@]server/project.git`.
- Or you can use the shorter scp-like syntax for the SSH protocol: `git clone [user@]server:project.git`.
- The Git Protocol Finally, we have the Git protocol.
- Running git clone http://example.com/project.git should be avoided for the same reason. • Running git clone https://example.com/project.git does not suffer from the same problem (unless the attacker can provide a TLS certificate for example.com).
- Running git clone git@example.com:project.git only suffers from this problem if you accept a wrong SSH key fingerprint.
- By convention, bare repository directory names end with the suffix .git, like so: `git clone --bare my_project my_project.git`.
- Let’s say you’ve set up a server called git.example.com to which you have SSH access, and you want to store all your Git repositories under the /srv/git directory.
- Assuming that /srv/git exists on that server, you can set up your new repository by copying your bare repository over: `scp -r my_project.git user@git.example.com:/srv/git`.
- At this point, other users who have SSH-based read access to the /srv/git directory on that server can clone your repository by running: `git clone user@git.example.com:/srv/git/my_project.git`.
- If a user SSHs into a server and has write access to the /srv/git/my_project.git directory, they will also automatically have push access.
- First, you create a git user account and a .ssh directory for that user. `sudo adduser git`.
- Now, you can set up an empty repository for them by running git init with the --bare option, which initializes the repository without a working directory: `cd /srv/git`.
- At this point, the others can clone it down and push changes back up just as easily: `git clone git@gitserver:/srv/git/project.git`.
- First, you need to get the Git source code, which GitWeb comes with, and generate the custom CGI script: `git clone https://git.kernel.org/pub/scm/git/git.git`.
- If you don’t have a local copy of the repository, you can simply do this: `git clone https://server/namespace/project.git`.

## Commands / code

```
$ git clone /srv/git/project.git
$ git clone file:///srv/git/project.git
$ git remote add local_proj /srv/git/project.git
$ cd /var/www/htdocs/
$ git clone --bare /path/to/git_project gitproject.git
$ cd gitproject.git
$ mv hooks/post-update.sample hooks/post-update
$ chmod a+x hooks/post-update
$ git clone https://example.com/gitproject.git
$ git clone ssh://[user@]server/project.git
$ git clone [user@]server:project.git
$ git clone --bare my_project my_project.git
$ cp -Rf my_project/.git my_project.git
$ scp -r my_project.git user@git.example.com:/srv/git
$ git clone user@git.example.com:/srv/git/my_project.git
$ ssh user@git.example.com
$ cd /srv/git/my_project.git
$ git init --bare --shared
$ cd ~/.ssh
$ ls
$ ssh-keygen -o
$ cat ~/.ssh/id_rsa.pub
$ sudo adduser git
$ su git
$ cd
$ mkdir .ssh && chmod 700 .ssh
$ touch .ssh/authorized_keys && chmod 600 .ssh/authorized_keys
public keys look something like this:
$ cat /tmp/id_rsa.john.pub
$ cat /tmp/id_rsa.john.pub >> ~/.ssh/authorized_keys
$ cat /tmp/id_rsa.josie.pub >> ~/.ssh/authorized_keys
$ cat /tmp/id_rsa.jessica.pub >> ~/.ssh/authorized_keys
$ cd /srv/git
$ mkdir project.git
$ cd project.git
$ git init --bare
$ cd myproject
$ git init
$ git add .
$ git commit -m 'Initial commit'
```

## Rules, tips and warnings

- Git on the Server At this point, you should be able to do most of the day-to-day tasks for which you’ll be using Git.
- Although you can technically push changes to and pull changes from individuals' repositories, doing so is discouraged because you can fairly easily confuse what they’re working on if you’re not careful.
- If you have a shared mounted filesystem, then you can clone, push to, and pull from a local filebased repository.
- For example, to clone a local repository, you can run something like this: `git clone /srv/git/project.git`.
- The main reason to specify the file:// prefix is if you want a clean copy of the repository with extraneous references or objects left out — generally after an import from another VCS or something similar (see Git Internals for maintenance tasks).
- We’ll use the normal path here because doing so is almost always faster.
- To add a local repository to an existing Git project, you can run something like this: `git remote add local_proj /srv/git/project.git`.
- Then, you can push to and pull from that remote via your new remote name local_proj as though you were doing so over a network.
- If you want to push from your laptop when you’re at home, you have to mount the remote disk, which can be difficult and slow compared to networkbased access.
- It’s important to mention that this isn’t necessarily the fastest option if you’re using a shared mount of some kind.
- Smart HTTP Smart HTTP operates very similarly to the SSH or Git protocols but runs over standard HTTPS ports and can use various HTTP authentication mechanisms, meaning it’s often easier on the user than something like SSH, since you can use things like username/password authentication rather than having to set up SSH keys.
- Instead of having to set up different URLs for these things, you can now use a single URL for both.
