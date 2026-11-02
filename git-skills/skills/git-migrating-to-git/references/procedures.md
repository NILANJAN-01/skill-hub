# More procedures: Migrating to Git

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
7. To move the tags to be proper Git tags, run:
   ```bash
   for t in $(git for-each-ref --format='%(refname:short)' refs/remotes/tags); do git
   ```
   Expected output (excerpt):
   ```text
   tag ${t/tags\//} $t && git branch -D -r $t; done
   ```
8. Next, move the rest of the references under `refs/remotes` to be local branches:
   ```bash
   for b in $(git for-each-ref --format='%(refname:short)' refs/remotes); do git branch
   ```
   Expected output (excerpt):
   ```text
   $b refs/remotes/$b && git branch -D -r $b; done
   ```
9. If you do not care anymore about the peg-revisions, simply remove them:
   ```bash
   for p in $(git for-each-ref --format='%(refname:short)' | grep @); do git branch -D
   ```
   Expected output (excerpt):
   ```text
   $p; done
   ```
10. Since `master` is more idiomatically Git, here’s how to remove the extra branch:
   ```bash
   git branch -d trunk
   ```
11. Here is an example of adding your server as a remote:
   ```bash
   git remote add origin git@my-git-server:myrepository.git
   ```
12. Because you want all your branches and tags to go up, you can now run this:
   ```bash
   git push origin --all
   git push origin --tags
   ```

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
7. This takes a bit (though it’s much faster than it would be over the network), and the output is fairly verbose:
   ```bash
   /tmp/fast-export/hg-fast-export.sh -r /tmp/hg-repo -A /tmp/authors
   ```
   Expected output (excerpt):
   ```text
   Loaded 4 authors
   master: Exporting full revision 1/22208 with 13/0/0 added/changed/removed files
   master: Exporting simple delta revision 2/22208 with 1/1/0 added/changed/removed files
   master: Exporting simple delta revision 3/22208 with 0/1/0 added/changed/removed files
   ```
8. Run:
   ```bash
   git shortlog -sn
   ```
   Expected output (excerpt):
   ```text
      369  Bob Jones
      365  Joe Smith
   ```
9. Now you’re ready to push the repository up to its new server-side home:
   ```bash
   git remote add origin git@my-git-server:myrepository.git
   git push origin --all
   ```

**Verify:** run `git shortlog -sn` - expect something like:
```text
   369  Bob Jones
   365  Joe Smith
```

**If it fails:** Hg-fast-export lets us fix this by turning each line into a rule: `"<input>"="<output>"`, mapping an `<input>` to an `<output>`.

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
7. where `convert_dir_to_date` is defined as:
   ```ruby
   def convert_dir_to_date(dir)
     if dir == 'current'
       return Time.now().to_i
     else
       dir = dir.gsub('back_', '')
       (year, month, day) = dir.split('_')
       return Time.local(year, month, day).to_i
     end
   end
   ```
8. The last piece of meta-information you need for each commit is the committer data, which you hardcode in a global variable:
   ```text
   $author = 'John Doe <john@example.com>'
   ```
9. The code looks like this:
   ```ruby
   # print the import information
   puts 'commit refs/heads/master'
   puts 'mark :' + mark
   puts "committer #{$author} #{date} -0700"
   export_data('imported from ' + dir)
   puts 'from :' + last_mark if last_mark
   ```
10. The commit message must be expressed in a special format:
   ```text
   data (size)\n(contents)
   ```
11. Because you need to use the same format to specify the file contents later, you create a helper method, `export_data`:
   ```ruby
   def export_data(string)
     print "data #{string.size}\n#{string}"
   end
   ```
12. Git will then record each snapshot appropriately:
   ```ruby
   puts 'deleteall'
   Dir.glob("**/*").each do |file|
     next if !File.file?(file)
     inline_data(file)
   end
   ```

_12 more step(s) in references/source-text.md._

**Verify:** run `git log -2` - expect something like:
```text
commit 3caa046d4aac682a55867132ccdfbe0d3fdee498
Author: John Doe <john@example.com>
Date:   Tue Jul 29 19:39:04 2014 -0700
```
