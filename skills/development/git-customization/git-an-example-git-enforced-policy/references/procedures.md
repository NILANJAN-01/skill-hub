# More procedures: An Example Git-Enforced Policy

### Server-Side Hook

**Goal:** Your first challenge is to enforce that each commit message adheres to a particular format.

**Steps:**

1. Here we’ll assume the connecting user is in the `$USER` environment variable, so your update script begins by gathering all the information you need:
   ```ruby
   #!/usr/bin/env ruby
   $refname = ARGV[0]
   $oldrev  = ARGV[1]
   $newrev  = ARGV[2]
   $user    = ENV['USER']
   puts "Enforcing Policies..."
   puts "(#{$refname}) (#{$oldrev[0,6]}) (#{$newrev[0,6]})"
   ```
2. So, to get a list of all the commit SHA-1s introduced between one commit SHA-1 and another, you can run something like this:
   ```bash
   git rev-list 538c33..d14fc7
   ```
   Expected output (excerpt):
   ```text
   d14fc7c847ab946ec39590d87783c69b031bdfb7
   9f585da4401b0a3999e84113824d15245c13f0be
   234071a1be950e2a8d078e6141f5cd20c1e61ad3
   dfa04c9ef3d5197182f13fb5b9b1fb7717d2222a
   ```
3. To get the raw commit data, you can use another plumbing command called `git cat-file`.
   ```bash
   git cat-file commit ca82a6
   ```
   Expected output (excerpt):
   ```text
   tree cfda3bf379e4f8dba8717dee55aab78aef7f4daf
   parent 085bb3bcb608e1e8451d4b2432f8ecbe6306e7e7
   author Scott Chacon <schacon@gmail.com> 1205815931 -0700
   committer Scott Chacon <schacon@gmail.com> 1240030591 -0700
   ```
4. You can do so with the `sed` command on Unix systems:
   ```bash
   git cat-file commit ca82a6 | sed '1,/^$/d'
   ```
   Expected output (excerpt):
   ```text
   Change the version number
   ```
5. The whole method looks like this:
   ```ruby
   $regex = /\[ref: (\d+)\]/
   # enforced custom commit message format
   def check_message_format
     missed_revs = `git rev-list #{$oldrev}..#{$newrev}`.split("\n")
     missed_revs.each do |rev|
       message = `git cat-file commit #{rev} | sed '1,/^$/d'`
       if !$regex.match(message)
         puts "[POLICY] Your message is not formatted correctly"
         exit 1
       end
     end
   end
   check_message_format
   ```
6. In this case, you have a couple of administrators, some documentation writers with access to the `doc` directory, and one developer who only has access to the `lib` and `tests` directories, and your ACL file looks like this:
   ```text
   avail|nickh,pjhyett,defunkt,tpw
   avail|usinclair,cdickens,ebronte|doc
   avail|schacon|lib
   avail|schacon|tests
   ```
7. Here is a method that gives you an associative array where the key is the user name and the value is an array of paths to which the user has write access:
   ```ruby
   def get_acl_access_data(acl_file)
     # read in ACL data
     acl_file = File.read(acl_file).split("\n").reject { |line| line == '' }
     access = {}
     acl_file.each do |line|
       avail, users, path = line.split('|')
       next unless avail == 'avail'
       users.split(',').each do |user|
         access[user] ||= []
         access[user] << path
       end
     end
     access
   end
   ```
8. On the ACL file you looked at earlier, this `get_acl_access_data` method returns a data structure that looks like this:
   ```text
   {"defunkt"=>[nil],
    "tpw"=>[nil],
    "nickh"=>[nil],
    "pjhyett"=>[nil],
    "schacon"=>["lib", "tests"],
    "cdickens"=>["doc"],
   ```
9. Run:
   ```text
    "usinclair"=>["doc"],
    "ebronte"=>["doc"]}
   ```
10. You can pretty easily see what files have been modified in a single commit with the `--name-only` option to the `git log` command (mentioned briefly in Git Basics):
   ```bash
   git log -1 --name-only --pretty=format:'' 9f585d
   ```
   Expected output (excerpt):
   ```text
   README
   lib/test.rb
   ```
11. If you use the ACL structure returned from the `get_acl_access_data` method and check it against the listed files in each of the commits, you can determine whether the user has access to push all of their commits:
   ```ruby
   # only allows certain users to modify certain subdirectories in a project
   def check_directory_perms
     access = get_acl_access_data('acl')
     # see if anyone is trying to push something they can't
     new_commits = `git rev-list #{$oldrev}..#{$newrev}`.split("\n")
     new_commits.each do |rev|
       files_modified = `git log -1 --name-only --pretty=format:'' #{rev}`.split("\n")
       files_modified.each do |path|
         next if path.size == 0
         has_file_access = false
         access[$user].each do |access_path|
           if !access_path  # user has access to everything
              || (path.start_with? access_path) # access to this path
             has_file_access = true
           end
         end
         if !has_file_access
           puts "[POLICY] You do not have access to push to #{path}"
           exit 1
         end
       end
     end
   end
   check_directory_perms
   ```
12. If you run `chmod u+x .git/hooks/update`, which is the file into which you should have put all this code, and then try to push a commit with a non-compliant message, you get something like this:
   ```bash
   git push -f origin master
   ```
   Expected output (excerpt):
   ```text
   Counting objects: 5, done.
   Compressing objects: 100% (3/3), done.
   Writing objects: 100% (3/3), 323 bytes, done.
   Total 3 (delta 1), reused 0 (delta 0)
   ```

_4 more step(s) in references/source-text.md._

**Verify:** run `git log -1 --name-only --pretty=format:'' 9f585d` - expect something like:
```text
README
lib/test.rb
```

### Client-Side Hooks

**Goal:** Client-Side Hooks

**Steps:**

1. If you have it read the message from the file passed as the first argument and compare that to the pattern, you can force Git to abort the commit if there is no match:
   ```ruby
   #!/usr/bin/env ruby
   message_file = ARGV[0]
   message = File.read(message_file)
   $regex = /\[ref: (\d+)\]/
   if !$regex.match(message)
     puts "[POLICY] Your message is not formatted correctly"
     exit 1
   end
   ```
2. If that script is in place (in `.git/hooks/commit-msg`) and executable, and you commit with a message that isn’t properly formatted, you see this:
   ```bash
   git commit -am 'Test'
   ```
   Expected output (excerpt):
   ```text
   [POLICY] Your message is not formatted correctly
   ```
3. Git allows you to commit:
   ```bash
   git commit -am 'Test [ref: 132]'
   ```
   Expected output (excerpt):
   ```text
   [master e05c914] Test [ref: 132]
    1 file changed, 1 insertions(+), 0 deletions(-)
   ```
4. If your project’s `.git` directory contains a copy of the ACL file you used previously, then the following `pre-commit` script will enforce those constraints for you:
   ```ruby
   #!/usr/bin/env ruby
   $user    = ENV['USER']
   # [ insert acl_access_data method from above ]
   # only allows certain users to modify certain subdirectories in a project
   def check_directory_perms
     access = get_acl_access_data('.git/acl')
     files_modified = `git diff-index --cached --name-only HEAD`.split("\n")
     files_modified.each do |path|
       next if path.size == 0
       has_file_access = false
       access[$user].each do |access_path|
       if !access_path || (path.index(access_path) == 0)
         has_file_access = true
       end
       if !has_file_access
         puts "[POLICY] You do not have access to push to #{path}"
         exit 1
       end
     end
   end
   check_directory_perms
   ```
5. You have to change the path to the ACL file from this:
   ```text
   access = get_acl_access_data('acl')
   ```
6. to this:
   ```text
   access = get_acl_access_data('.git/acl')
   ```
7. Instead of:
   ```text
   files_modified = `git log -1 --name-only --pretty=format:'' #{ref}`
   ```
8. you have to use:
   ```text
   files_modified = `git diff-index --cached --name-only HEAD`
   ```
9. Presumably, the server is already configured with
   ```text
   receive.denyDeletes
   ```
10. If it sees one that is reachable from one of your remote references, it aborts the rebase.
   ```ruby
   #!/usr/bin/env ruby
   base_branch = ARGV[0]
   if ARGV[1]
     topic_branch = ARGV[1]
   else
     topic_branch = "HEAD"
   end
   target_shas = `git rev-list #{base_branch}..#{topic_branch}`.split("\n")
   remote_refs = `git branch -r`.split("\n").map { |r| r.strip }
   target_shas.each do |sha|
     remote_refs.each do |remote_ref|
       shas_pushed = `git rev-list ^#{sha}^@ refs/remotes/#{remote_ref}`
       if shas_pushed.split("\n").include?(sha)
         puts "[POLICY] Commit #{sha} has already been pushed to #{remote_ref}"
         exit 1
   ```
11. Run:
   ```ruby
       end
     end
   end
   ```
12. You get a list of commits that have already been pushed up by running this:
   ```text
   `git rev-list ^#{sha}^@ refs/remotes/#{remote_ref}`
   ```

**If it fails:** That way, they can correct any problems before committing and before those issues become more difficult to fix.
