# More procedures: Git as a Client

### Git and Subversion

**Goal:** This tool allows you to use Git as a valid client to a Subversion server, so you can use all the local features of Git and then push to a Subversion server as if you were using Subversion locally.

**Steps:**

1. To follow along, you first need to create a new local Subversion repository:
   ```bash
   mkdir /tmp/test-svn
   svnadmin create /tmp/test-svn
   ```
2. Then, enable all users to change revprops – the easy way is to add a `pre-revprop-change` script that always exits 0:
   ```bash
   cat /tmp/test-svn/hooks/pre-revprop-change
   chmod +x /tmp/test-svn/hooks/pre-revprop-change
   ```
   Expected output (excerpt):
   ```text
   #!/bin/sh
   exit 0;
   ```
3. You can now sync this project to your local machine by calling `svnsync init` with the to and from repositories.
   ```bash
   svnsync init file:///tmp/test-svn \
   http://your-svn-server.example.org/svn/
   ```
4. You can then clone the code by running:
   ```bash
   svnsync sync file:///tmp/test-svn
   ```
   Expected output (excerpt):
   ```text
   Committed revision 1.
   Copied properties for revision 1.
   Transmitting file data .............................[...]
   Committed revision 2.
   ```
5. Subversion repository:
   ```bash
   git svn clone file:///tmp/test-svn -T trunk -b branches -t tags
   ```
   Expected output (excerpt):
   ```text
   Initialized empty Git repository in /private/tmp/progit/test-svn/.git/
   r1 = dcbfb5891860124cc2e8cc616cded42624897125 (refs/remotes/origin/trunk)
       A   m4/acx_pthread.m4
       A   m4/stl_hash.m4
   ```
6. The following command is equivalent:
   ```bash
   git svn clone file:///tmp/test-svn -s
   ```
7. At this point, you should have a valid Git repository that has imported your branches and tags:
   ```bash
   git branch -a
   ```
   Expected output (excerpt):
   ```text
   * master
     remotes/origin/my-calc-branch
     remotes/origin/tags/2.0.2
     remotes/origin/tags/release-2.0.1
   ```
8. Let’s take a closer look with the Git plumbing command `show-ref`:
   ```bash
   git show-ref
   ```
   Expected output (excerpt):
   ```text
   556a3e1e7ad1fde0a32823fc7e4d046bcfd86dae refs/heads/master
   0fb585761df569eaecd8146c71e58d70147460a2 refs/remotes/origin/my-calc-branch
   bfd2d79303166789fc73af4046651a4b35c12f0b refs/remotes/origin/tags/2.0.2
   285c2b2e36e467dd4d91c8e3c0c0e1750b3fe8ca refs/remotes/origin/tags/release-2.0.1
   ```
9. Git doesn’t do this when it clones from a Git server; here’s what a repository with tags looks like after a fresh clone:
   ```bash
   git show-ref
   ```
   Expected output (excerpt):
   ```text
   c3dcbe8488c6240392e8a5d7553bbffcb0f94ef0 refs/remotes/origin/master
   32ef1d1c7cc8c603ab78416262cc421b80a8c2df refs/remotes/origin/branch-1
   75f703a3580a9b81ead89fe1138e6da858c5ba18 refs/remotes/origin/branch-2
   23f8588dde934e8f33c263c6d8359b2ae095f863 refs/tags/v0.1.0
   ```
10. If you edit one of the files and commit it, you have a commit that exists in Git locally that doesn’t exist on the Subversion server:
   ```bash
   git commit -am 'Adding git-svn instructions to the README'
   ```
   Expected output (excerpt):
   ```text
   [master 4af61fd] Adding git-svn instructions to the README
    1 file changed, 5 insertions(+)
   ```
11. To push to a Subversion server, you run the `git svn dcommit` command:
   ```bash
   git svn dcommit
   ```
   Expected output (excerpt):
   ```text
   Committing to file:///tmp/test-svn/trunk ...
       M   README.txt
   Committed r77
       M   README.txt
   ```
12. Run:
   ```text
   refs/remotes/origin/trunk
   Resetting to the latest refs/remotes/origin/trunk
   ```

_14 more step(s) in references/source-text.md._

**Verify:** run `git log -1` - expect something like:
```text
commit 95e0222ba6399739834380eb10afcd73e0670bc5
Author: ben <ben@0b684db3-b064-4277-89d1-21af03df0a68>
Date:   Thu Jul 24 03:08:36 2014 +0000
    Adding git-svn instructions to the README
    git-svn-id: file:///tmp/test-svn/trunk@77 0b684db3-b064-4277-89d1-21af03df0a68
```

**If it fails:** To resolve this situation, you can run `git svn rebase`, which pulls down any changes on the server that you don’t have yet and rebases any work you have on top of what is on the server:

### Git and Mercurial

**Goal:** The last thing you’ll need is the Mercurial client.

**Steps:**

1. This basically entails dropping its file somewhere in your path, like so:
   ```bash
   curl -o ~/bin/git-remote-hg \
   https://raw.githubusercontent.com/felipec/git-remote-hg/master/git-remote-hg
   chmod +x ~/bin/git-remote-hg
   ```
2. If you have Python installed, this is as simple as:
   ```bash
   pip install mercurial
   ```
3. Mercurial repository can act this way, so we’ll just use the "hello world" repository everyone uses to learn Mercurial:
   ```bash
   hg clone http://selenic.com/repo/hello /tmp/hello
   ```
4. As always with Git, first we clone:
   ```bash
   git clone hg::/tmp/hello /tmp/hello-git
   cd /tmp/hello-git
   git log --oneline --graph --decorate
   ```
   Expected output (excerpt):
   ```text
   * ac7955c (HEAD, origin/master, origin/branches/default, origin/HEAD,
   refs/hg/origin/branches/default, refs/hg/origin/bookmarks/master, master) Create a
   makefile
   * 65bb417 Create a standard 'hello, world' program
   ```
5. Let’s take a look at what’s actually in the `.git` directory:
   ```bash
   tree .git/refs
   ```
   Expected output (excerpt):
   ```text
   .git/refs
   ├── heads
   │   └── master
   ├── hg
   ```
6. Run:
   ```text
   │       └── HEAD
   └── tags
   9 directories, 5 files
   ```
7. Let’s explore a bit:
   ```bash
   cat notes/hg
   git cat-file -p d4c10386...
   git ls-tree 1781c96...
   git cat-file -p ac9117f
   ```
   Expected output (excerpt):
   ```text
   d4c10386...
   tree 1781c96...
   author remote-hg <> 1408066400 -0800
   committer remote-hg <> 1408066400 -0800
   ```
8. Fortunately, Git has a way to ignore files that’s local to an on-disk repository, and the Mercurial format is compatible with Git, so you just have to copy it over:
   ```bash
   cp .hgignore .git/info/exclude
   ```
9. Here’s what our repository looks like right now:
   ```bash
   git log --oneline --graph --decorate
   ```
   Expected output (excerpt):
   ```text
   * ba04a2a (HEAD, master) Update makefile
   * d25d16f Goodbye
   * ac7955c (origin/master, origin/branches/default, origin/HEAD,
   refs/hg/origin/branches/default, refs/hg/origin/bookmarks/master) Create a makefile
   ```
10. Let’s see if anyone else has been doing important work at the same time:
   ```bash
   git fetch
   git log --oneline --graph --decorate --all
   ```
   Expected output (excerpt):
   ```text
   From hg::/tmp/hello
      ac7955c..df85e87  master     -> origin/master
      ac7955c..df85e87  branches/default -> origin/branches/default
   * 7b07969 (refs/notes/hg) Notes for default
   ```
11. The rest is what we expected; `origin/master` has advanced by one commit, and our history has now diverged.
   ```bash
   git merge origin/master
   git log --oneline --graph --decorate
   ```
   Expected output (excerpt):
   ```text
   Auto-merging hello.c
   Merge made by the 'recursive' strategy.
    hello.c | 2 +-
    1 file changed, 1 insertion(+), 1 deletion(-)
   ```
12. Run:
   ```text
   documentation
   * | ba04a2a Update makefile
   * | d25d16f Goodbye
   |/
   * ac7955c Create a makefile
   * 65bb417 Create a standard 'hello, world' program
   ```

_8 more step(s) in references/source-text.md._

**Verify:** run `hg log --style compact -G` - expect something like:
```text
o  10[tip]   99611176cbc9   2014-08-14 20:21 -0700   ben
|    A permanent change
|
o  9   f23e12f939c3   2014-08-14 20:01 -0700   ben
|    Add some documentation
|
```

### Git and Perforce

**Goal:** The second is git-p4, a client-side bridge that lets you use Git as a Perforce client, without requiring any reconfiguration of the Perforce server.

**Steps:**

1. Then use these commands to create a user:
   ```bash
   p4 -p localhost:1666 -u super user -f john
   p4 -p localhost:1666 -u john passwd
   exit
   ```
2. If this is going to be a permanent installation, consult the Perforce Git Fusion manual to install a different certificate; for our example purposes, this will suffice:
   ```bash
   export GIT_SSL_NO_VERIFY=true
   ```
3. Now we can test that everything is working.
   ```bash
   git clone https://10.0.1.254/Talkhouse
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'Talkhouse'...
   Username for 'https://10.0.1.254': john
   Password for 'https://john@10.0.1.254':
   remote: Counting objects: 630, done.
   ```
4. The file structure looks like this:
   ```bash
   tree
   ```
   Expected output (excerpt):
   ```text
   .
   ├── objects
   │   ├── repos
   │   │   └── [...]
   ```
5. Let’s take a look at the file in the root:
   ```ini
   [repo-creation]
   charset = utf8
   [git-to-perforce]
   change-owner = author
   enable-git-branch-creation = yes
   enable-swarm-reviews = yes
   enable-git-merge-commits = yes
   enable-git-submodules = yes
   preflight-commit = none
   ignore-author-permissions = no
   read-permission-check = none
   git-merge-avoidance-after-change-num = 12107
   [perforce-to-git]
   http-url = none
   ssh-url = none
   [@features]
   imports = False
   chunked-push = False
   matrix2 = False
   parallel-push = False
   [authentication]
   email-case-sensitivity = no
   ```
6. You’ll also see sections that look like this:
   ```ini
   [Talkhouse-master]
   git-branch-name = master
   view = //depot/Talkhouse/main-dev/... ...
   ```
7. More than one mapping can be specified, like in this example:
   ```ini
   [multi-project-mapping]
   git-branch-name = master
   view = //depot/project1/main/... project1/...
          //depot/project2/mainline/... project2/...
   ```
8. In most cases, this behavior will do just fine, but consider the following mapping file:
   ```text
   john john@example.com "John Doe"
   john johnny@appleseed.net "John Doe"
   bob employeeX@example.com "Anon X. Mouse"
   joe employeeY@example.com "Anon Y. Mouse"
   ```
9. We’ll assume we’ve mapped in the “Jam” project using a configuration file as shown above, which we can clone like this:
   ```bash
   git clone https://10.0.1.254/Jam
   git branch -a
   git log --oneline --decorate --graph --all
   ```
   Expected output (excerpt):
   ```text
   Cloning into 'Jam'...
   Username for 'https://10.0.1.254': john
   Password for 'https://john@10.0.1.254':
   remote: Counting objects: 2070, done.
   ```
10. Run:
   ```ini
   * 0a38c33 (origin/rel2.1) Create Jam 2.1 release branch.
   | * d254865 (HEAD, origin/master, origin/HEAD, master) Upgrade to latest metrowerks on
   Beos -- the Intel one.
   | * bd2f54a Put in fix for jam's NT handle leak.
   | * c0f29e7 Fix URL in a jam doc
   | * cc644ac Radstone's lynx port.
   [...]
   ```
11. Let’s do a bit of work, and create a couple of new commits:
   ```bash
   git log --oneline --decorate --graph --all
   ```
   Expected output (excerpt):
   ```text
   * cfd46ab (HEAD, master) Add documentation for new feature
   * a730d77 Whitespace
   * d254865 (origin/master, origin/HEAD) Upgrade to latest metrowerks on Beos -- the
   Intel one.
   ```
12. Now let’s check if anyone else has been working:
   ```bash
   git fetch
   git log --oneline --decorate --graph --all
   ```
   Expected output (excerpt):
   ```text
   remote: Counting objects: 5, done.
   remote: Compressing objects: 100% (3/3), done.
   remote: Total 3 (delta 2), reused 0 (delta 0)
   Unpacking objects: 100% (3/3), done.
   ```

_22 more step(s) in references/source-text.md._

**Verify:** run `git log --oneline --all --graph --decorate` - expect something like:
```text
* 3be6fd8 (HEAD, master) Correct email address
*   1dcbf21 Merge remote-tracking branch 'p4/master'
```
