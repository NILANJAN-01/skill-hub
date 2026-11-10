# More procedures: Setting Up the Server

### Setting Up the Server

**Goal:** With this method, you can quickly get a read/write Git server up and running for a handful of developers.

**Steps:**

1. First, you create a `git` user account and a `.ssh` directory for that user.
   ```bash
   sudo adduser git
   su git
   cd
   mkdir .ssh && chmod 700 .ssh
   touch .ssh/authorized_keys && chmod 600 .ssh/authorized_keys
   ```
2. Again, the public keys look something like this:
   ```bash
   cat /tmp/id_rsa.john.pub
   ```
   Expected output (excerpt):
   ```text
   ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCB007n/ww+ouN4gSLKssMxXnBOvf9LGt4L
   ojG6rs6hPB09j9R/T17/x4lhJA0F3FR1rP6kYBRsWj2aThGw6HXLm9/5zytK6Ztg3RPKK+4k
   Yjh6541NYsnEAZuXz0jTTyAUfrtU3Z5E003C4oxOj6H0rfIF1kKI9MAQLMdpGW1GYEIgS9Ez
   Sdfd8AcCIicTDWbqLAcU4UpkaX8KyGlLwsNuuGztobF8m72ALC/nLF6JLtPofwFBlgc+myiv
   ```
3. You just append them to the `git` user’s `authorized_keys` file in its `.ssh` directory:
   ```bash
   cat /tmp/id_rsa.john.pub >> ~/.ssh/authorized_keys
   cat /tmp/id_rsa.josie.pub >> ~/.ssh/authorized_keys
   cat /tmp/id_rsa.jessica.pub >> ~/.ssh/authorized_keys
   ```
4. Now, you can set up an empty repository for them by running `git init` with the `--bare` option, which initializes the repository without a working directory:
   ```bash
   cd /srv/git
   mkdir project.git
   cd project.git
   git init --bare
   ```
   Expected output (excerpt):
   ```text
   Initialized empty Git repository in /srv/git/project.git/
   ```
5. If you’re running it internally, and you set up DNS for `gitserver` to point to that server, then you can use the commands pretty much as is (assuming that `myproject` is an existing project with files in it):
   ```bash
   cd myproject
   git init
   git add .
   git commit -m 'Initial commit'
   git remote add origin git@gitserver:/srv/git/project.git
   git push origin master
   ```
6. At this point, the others can clone it down and push changes back up just as easily:
   ```bash
   git clone git@gitserver:/srv/git/project.git
   ```
7. Run:
   ```bash
   cd project
   vim README
   git commit -am 'Fix for README file'
   git push origin master
   ```
8. To do so, you must first add the full pathname of the `git-shell` command to `/etc/shells` if it’s not already there:
   ```bash
   cat /etc/shells   # see if git-shell is already in there. If not...
   which git-shell   # make sure git-shell is installed on your system.
   sudo -e /etc/shells  # and add the path to git-shell from last command
   ```
9. Now you can edit the shell for a user using `chsh <username> -s <shell>`:
   ```bash
   sudo chsh git -s $(which git-shell)
   ```
10. If you try, you’ll see a login rejection like this:
   ```bash
   ssh git@gitserver
   ```
   Expected output (excerpt):
   ```text
   fatal: Interactive git shell is not enabled.
   hint: ~/git-shell-commands should exist and have read and execute access.
   Connection to gitserver closed.
   ```
11. If you want to prevent that, you can edit the `authorized_keys` file and prepend the following options to each key you’d like to restrict:
   ```text
   no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty
   ```
12. The result should look like this:
   ```bash
   cat ~/.ssh/authorized_keys
   ```
   Expected output (excerpt):
   ```text
   no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-rsa
   AAAAB3NzaC1yc2EAAAADAQABAAABAQCB007n/ww+ouN4gSLKssMxXnBOvf9LGt4LojG6rs6h
   ```

_1 more step(s) in references/source-text.md._

**Verify:** run `cat ~/.ssh/authorized_keys` - expect something like:
```text
no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-rsa
AAAAB3NzaC1yc2EAAAADAQABAAABAQCB007n/ww+ouN4gSLKssMxXnBOvf9LGt4LojG6rs6h
```
