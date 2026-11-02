---
name: git-migrating-to-git
description: "Migrating to Git playbook extracted from \"Pro Git\". If you want to map this to better Git author data, you need a mapping from the Subversion users to the Git authors. Use when the user asks about migrating to git, git svn, git tags, git fast-import, git server, data, directory; or mentions cd, git log, ls, for --format, git remote, git push --all."
---

# Migrating to Git

If you want to map this to better Git author data, you need a mapping from the Subversion users to the Git authors.

_Built from "Pro Git" (pages 405-419) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **migrating to git** (git svn, git tags, git fast-import, git server, data).
- The user wants to run or understand `cd`.
- The user wants to run or understand `git log`.
- The user wants to run or understand `ls`.
- The user wants to run or understand `for --format`.

## When NOT to use

- For git as a client, use the `git-as-a-client` skill instead.
- For contributing to a project, use the `git-distributed-git-contributing-to-a-project` skill instead.
- For maintaining a project, use the `git-distributed-git-maintaining-a-project` skill instead.

## Key concepts

- All your branches and tags should be on your new Git server in a nice, clean import.
- Mercurial is a bit more forgiving than Git for what it will put in the author field for changesets, so this is a good time to clean house.
- In order to import a Git directory, you need to review how Git stores its data.
- All you have to do is tell `fast-import` what the content snapshots are, what commit data points to them, and the order they go in.
- “Mark” is the `fast-import` term for an identifier you give to a commit; as you create commits, you give each one a mark that you can use to link to it from other commits.
- Note: Because many systems think of their revisions as changes from one commit to another, fast-import can also take commands with each commit to specify which files have been added, removed, or modified and what the new contents are.
- To run the importer, pipe this output through `git fast-import` while in the Git directory you want to import into.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `for p in $(git for-each-ref --format='%(refname:short)' | grep @); do git branch -D`
  - `git filter-branch --msg-filter 'sed -e "/^\[git-p4:/d"'`
  - `git reset --hard master`
- That generates the log output in XML format, then keeps only the lines with author information, discards duplicates, strips out the XML tags.

## Procedures

### Subversion

**Goal:** Subversion

**Steps:**

1. Create a file called `users.txt` that has this mapping in a format like this:
   ```text
   schacon = Scott Chacon <schacon@geemail.com>
   selse = Someo Nelse <selse@geemail.com>
   ```
2. To get a list of the author names that SVN uses, you can run this:
   ```bash
   svn log --xml --quiet | grep author | sort -u | \
   perl -pe 's/.*>(.*?)<.*/$1 = /'
   ```
3. This makes your `import` command look like this:
   ```bash
   git svn clone http://my-project.googlecode.com/svn/ \
   --authors-file=users.txt --no-metadata --prefix "" -s my_project
   cd my_project
   ```
4. Instead of commits that look like this:
   ```text
   commit 37efa680e8473b615de980fa935944215428a35a
   Author: schacon <schacon@4c93b258-373f-11de-be05-5f7a86268029>
   Date:   Sun May 3 00:12:22 2009 +0000
       fixed install - go to trunk
       git-svn-id: https://my-project.googlecode.com/svn/trunk@94 4c93b258-373f-11de-
       be05-5f7a86268029
   ```
5. they look like this:
   ```text
   commit 03a8785f44c8ea5cdb0e8834b7c8e6c469be2ff2
   ```
6. Run:
   ```text
   Author: Scott Chacon <schacon@geemail.com>
   Date:   Sun May 3 00:12:22 2009 +0000
       fixed install - go to trunk
   ```

_6 more step(s) in references/procedures.md._

### Mercurial

**Goal:** Mercurial

**Steps:**

1. Since Mercurial and Git have fairly similar models for representing versions, and since Git is a bit more flexible, converting a repository from Mercurial to Git is fairly straightforward, using a tool called "hg-fast-export", which you’ll need a copy of:
   ```bash
   git clone https://github.com/frej/fast-export.git
   ```
2. The first step in the conversion is to get a full clone of the Mercurial repository you want to convert:
   ```bash
   hg clone <remote repo URL> /tmp/hg-repo
   ```
3. Generating this is a one-line command in a `bash` shell:
   ```bash
   cd /tmp/hg-repo
   hg log | grep user: | sort | uniq | sed 's/user: *//' > ../authors
   ```
4. This will take a few seconds, depending on how long your project’s history is, and afterwards the `/tmp/authors` file will look something like this:
   ```text
   bob
   bob@localhost
   bob <bob@company.com>
   bob jones <bob <AT> company <DOT> com>
   Bob Jones <bob@company.com>
   Joe Smith <joe@company.com>
   ```
5. In this example, we want our file to look like this:
   ```text
   "bob"="Bob Jones <bob@company.com>"
   "bob@localhost"="Bob Jones <bob@company.com>"
   "bob <bob@company.com>"="Bob Jones <bob@company.com>"
   "bob jones <bob <AT> company <DOT> com>"="Bob Jones <bob@company.com>"
   ```
6. The next step is to create our new Git repository, and run the export script:
   ```bash
   git init /tmp/converted
   cd /tmp/converted
   /tmp/fast-export/hg-fast-export.sh -r /tmp/hg-repo -A /tmp/authors
   ```

_3 more step(s) in references/procedures.md._

**Verify:** run `git shortlog -sn` - expect something like:
```text
   369  Bob Jones
   365  Joe Smith
```

**If it fails:** Hg-fast-export lets us fix this by turning each line into a rule: `"<input>"="<output>"`, mapping an `<input>` to an `<output>`.

### Perforce

**Goal:** Perforce

**Steps:**

1. To set up your client, you must export the P4PORT environment variable to point to the Perforce depot:
   ```bash
   export P4PORT=public.perforce.com:1666
   ```
2. Run the `git p4 clone` command to import the Jam project from the Perforce server, supplying the depot and project path and the path into which you want to import the project:
   ```bash
   git-p4 clone //guest/perforce_software/jam@all p4import
   ```
   Expected output (excerpt):
   ```text
   Importing from //guest/perforce_software/jam@all into p4import
   Initialized empty Git repository in /private/tmp/p4import/.git/
   Import destination: refs/remotes/p4/master
   Importing revision 9957 (100%)
   ```
3. If you go to the `p4import` directory and run `git log`, you can see your imported work:
   ```bash
   git log -2
   ```
   Expected output (excerpt):
   ```text
   commit e5da1c909e5db3036475419f6379f2c73710c4e6
   Author: giles <giles@giles@perforce.com>
   Date:   Wed Feb 8 03:13:27 2012 -0800
       Correction to line 355; change </UL> to </OL>.
   ```
4. You can use `git filter-branch` to remove the identifier strings en masse:
   ```bash
   git filter-branch --msg-filter 'sed -e "/^\[git-p4:/d"'
   ```
   Expected output (excerpt):
   ```text
   Rewrite e5da1c909e5db3036475419f6379f2c73710c4e6 (125/125)
   Ref 'refs/heads/master' was rewritten
   ```
5. If you run `git log`, you can see that all the SHA-1 checksums for the commits have changed, but the `git-p4` strings are no longer in the commit messages:
   ```bash
   git log -2
   ```
   Expected output (excerpt):
   ```text
   commit b17341801ed838d97f7800a54a6f9b95750839b7
   Author: giles <giles@giles@perforce.com>
   Date:   Wed Feb 8 03:13:27 2012 -0800
       Correction to line 355; change </UL> to </OL>.
   ```

**Verify:** run `git log -2` - expect something like:
```text
commit b17341801ed838d97f7800a54a6f9b95750839b7
Author: giles <giles@giles@perforce.com>
Date:   Wed Feb 8 03:13:27 2012 -0800
    Correction to line 355; change </UL> to </OL>.
commit 3e68c2e26cd89cb983eb52c024ecdfba1d6b3fff
Author: kwirth <kwirth@perforce.com>
```

### A Custom Importer

**Goal:** A Custom Importer

**Steps:**

1. Your directory structure looks like this:
   ```bash
   ls /opt/import_from
   ```
   Expected output (excerpt):
   ```text
   back_2014_01_02
   back_2014_01_04
   back_2014_01_14
   back_2014_02_03
   ```
2. Your basic main loop looks like this:
   ```ruby
   last_mark = nil
   # loop through the directories
   Dir.chdir(ARGV[0]) do
     Dir.glob("*").each do |dir|
       next if File.file?(dir)
       # move into the target directory
       Dir.chdir(dir) do
         last_mark = print_export(dir, last_mark)
       end
     end
   end
   ```
3. So, the first thing to do in your `print_export` method is generate a mark from the directory name:
   ```text
   mark = convert_dir_to_mark(dir)
   ```
4. Your method looks like this:
   ```ruby
   $marks = []
   def convert_dir_to_mark(dir)
     if !$marks.include?(dir)
       $marks << dir
     end
     ($marks.index(dir) + 1).to_s
   ```
5. Run:
   ```ruby
   end
   ```
6. The next line in your `print_export` file is:
   ```text
   date = convert_dir_to_date(dir)
   ```

_18 more step(s) in references/procedures.md._

**Verify:** run `git log -2` - expect something like:
```text
commit 3caa046d4aac682a55867132ccdfbe0d3fdee498
Author: John Doe <john@example.com>
Date:   Tue Jul 29 19:39:04 2014 -0700
```

More procedures in [references/procedures.md](references/procedures.md):

- Subversion
- Mercurial
- A Custom Importer

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git log` | Now, you can run `git log` to see your new history | `git log -2` |
| `for --format` | To move the tags to be proper Git tags, run | `for t in $(git for-each-ref --format='%(refname:short)' refs/remotes/tags); do git` |
| `git remote` | Here is an example of adding your server as a remote | `git remote add origin git@my-git-server:myrepository.git` |
| `git push --all` | Because you want all your branches and tags to go up, you can now run this | `git push origin --all` |
| `git init` | You can create a new directory and then run `git init` in it for a starting point, and then run your script | `git init` |
| `/tmp/fast-export/hg-fast-export.sh -r -A` | The next step is to create our new Git repository, and run the export script | `/tmp/fast-export/hg-fast-export.sh -r /tmp/hg-repo -A /tmp/authors` |
| `ruby` | As we did in An Example Git-Enforced Policy, we’ll write this in Ruby, because it’s what we generally work with and it tends to be easy to read. | `ruby import.rb /opt/import_from` |
| `svn log --xml --quiet` | To get a list of the author names that SVN uses, you can run this | `svn log --xml --quiet \| grep author \| sort -u \| \` |
| `git svn --authors-file --no-metadata` | This makes your `import` command look like this | `git svn clone http://my-project.googlecode.com/svn/ \` |
| `for --format -D` | If you do not care anymore about the peg-revisions, simply remove them | `for p in $(git for-each-ref --format='%(refname:short)' \| grep @); do git branch -D` |
| `git branch -d` | Since `master` is more idiomatically Git, here’s how to remove the extra branch | `git branch -d trunk` |
| `git push --tags` | Because you want all your branches and tags to go up, you can now run this | `git push origin --tags` |
| `git clone` | Since Mercurial and Git have fairly similar models for representing versions, and since Git is a bit more flexible, converting a repository from Mercurial to Git is fairly straightforward, using a tool called "hg-fast-export", which you’ll need a copy of | `git clone https://github.com/frej/fast-export.git` |
| `hg clone` | The first step in the conversion is to get a full clone of the Mercurial repository you want to convert | `hg clone <remote repo URL> /tmp/hg-repo` |
| `hg log` | Generating this is a one-line command in a `bash` shell | `hg log \| grep user: \| sort \| uniq \| sed 's/user: *//' > ../authors` |
| `git shortlog -sn` | This takes a bit (though it’s much faster than it would be over the network), and the output is fairly verbose | `git shortlog -sn` |
| `export` | Since Mercurial and Git have fairly similar models for representing versions, and since Git is a bit more flexible, converting a repository from Mercurial to Git is fairly straightforward, using a tool called "hg-fast-export", which you’ll need a copy of | `export P4PORT=public.perforce.com:1666` |
| `git-p4 clone` | Run the `git p4 clone` command to import the Jam project from the Perforce server, supplying the depot and project path and the path into which you want to import the project | `git-p4 clone //guest/perforce_software/jam@all p4import` |
| `git filter-branch --msg-filter -e` | You can use `git filter-branch` to remove the identifier strings en masse | `git filter-branch --msg-filter 'sed -e "/^\[git-p4:/d"'` |
| `git reset --hard` | To get them, you must reset your branch to where `master` is now | `git reset --hard master` |

## Decision guide

- If you want to map this to better Git author data, you need a mapping from the Subversion users to the Git authors.
- If all the usernames look fine, we won’t need this file at all.
- If your system isn’t one of the above, you should look for an importer online – quality importers are available for many other systems, including CVS, Clear Case, Visual Source Safe, even a directory of archives.
- If none of these tools works for you, you have a more obscure tool, or you otherwise need a more custom importing process, you should use `git fast-import`.
- If this is better suited to your data, check the `fast-import` man page for details about how to provide your data in this manner.

## Troubleshooting

- **Note:** If you’re trying this on a Windows machine, this is the point where you’ll run into trouble.
- **Note:** https://learn.microsoft.com/en-us/azure/devops/repos/git/perform-migration-from-svn-to-git.
- **Note:** You need to keep the metadata when you want to mirror commits made in the Git repository back into the original SVN repository. If you don’t want the synchronization in your commit log, feel free to omit the `--no-metadata` parameter.
- **Note:** In order to follow along, you’ll need a Perforce depot to connect with. We’ll be using the public depot at public.perforce.com for our examples, but you can use any depot you have access to.
- **Note:** If you are running on Windows you’ll need to make sure that you add one extra step. As mentioned before, Windows uses CRLF for new line characters while `gitfast-import` expects only LF. To get around this problem and make `git fast-import` happy, you need to tell ruby to use LF instead of CRLF:

## Related skills

- `git-as-a-client` - Git as a Client
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project
- `git-distributed-git-maintaining-a-project` - Maintaining a Project
- `git-configuration` - Git Configuration

## Source

"Pro Git", pages 405-419. Sections: Migrating to Git; Migrating to Git > Subversion; Migrating to Git > Mercurial; Migrating to Git > Perforce; Migrating to Git > A Custom Importer.
