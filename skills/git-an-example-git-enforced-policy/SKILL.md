---
name: git-an-example-git-enforced-policy
description: "Enforce commit-message format, file ACLs and push rules with git hook scripts. Use when handling a team commit or push policy."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "An Example Git-Enforced Policy"
  category: git-customization
  source: "Pro Git, 2nd edition"
  pages: "363-372"
---

# An Example Git-Enforced Policy

You’ll build client scripts that help the developer know if their push will be rejected and server scripts that actually enforce the policies.

_Built from "Pro Git" (pages 363-372) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **an example git-enforced policy** (commit message, acl file, update script, list, scripts).
- The user wants to run or understand `git cat-file`.
- The user wants to run or understand `git commit -am`.
- The user wants to run or understand `git rev-list`.
- The user wants to run or understand `git log --name-only --pretty`.
- The user sees an error like `error: hooks/update exited with error code 1`.
- The user sees an error like `! [remote rejected] master -> master (hook declined)`.

## When NOT to use

- For git hooks, use the `git-hooks` skill instead.
- For git configuration, use the `git-configuration` skill instead.
- For git as a client, use the `git-as-a-client` skill instead.

## Key concepts

- However, any language will work – all the sample hook scripts distributed with Git are in either Perl or Bash, so you can also see plenty of examples of hooks in those languages by looking at the samples.
- Your first challenge is to enforce that each commit message adheres to a particular format.
- You must look at each commit being pushed up, see if that string is in the commit message, and, if the string is absent from any of the commits, exit non-zero so the push is rejected.
- Putting that in your `update` script will reject updates that contain commits that have messages that don’t adhere to your rule.
- To enforce this, you’ll write those rules to a file named `acl` that lives in your bare Git repository on the server.
- You’ll have the `update` hook look at those rules, see what files are being introduced for all the commits being pushed, and determine whether the user doing the push has access to update all those files.
- The downside to this approach is the whining that will inevitably result when your users' commit pushes are rejected.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.
- These commands can rewrite history or discard work. Ask the user to confirm first and create a safety net (backup branch, stash or copy) before running them:
  - `git push -f origin master`
- Don’t judge – it’s easier to demonstrate this way.
- From now on, as long as that `update` script is there and executable, your repository will never have a commit message without your pattern in it, and your users will be sandboxed.
- The main drawback to this approach is that it can be very slow and is often unnecessary – if you don’t try to force the push with `-f`, the server will warn you and not accept the push.

## Procedures

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

_10 more step(s) in references/procedures.md._

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
   # ... (full listing in references)
   ```
5. You have to change the path to the ACL file from this:
   ```text
   access = get_acl_access_data('acl')
   ```
6. to this:
   ```text
   access = get_acl_access_data('.git/acl')
   ```

_6 more step(s) in references/procedures.md._

**If it fails:** That way, they can correct any problems before committing and before those issues become more difficult to fix.

More procedures in [references/procedures.md](references/procedures.md):

- Server-Side Hook
- Client-Side Hooks

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git cat-file` | To get the raw commit data, you can use another plumbing command called `git cat-file`. | `git cat-file commit ca82a6` |
| `git commit -am` | If that script is in place (in `.git/hooks/commit-msg`) and executable, and you commit with a message that isn’t properly formatted, you see this | `git commit -am 'Test'` |
| `git rev-list` | You get a list of new commits being pushed to your server with `git rev-list`. | `git rev-list 538c33..d14fc7` |
| `git log --name-only --pretty` | You can pretty easily see what files have been modified in a single commit with the `--name-only` option to the `git log` command (mentioned briefly in Git Basics) | `git log -1 --name-only --pretty=format:'' 9f585d` |
| `git push -f` | If you run `chmod u+x .git/hooks/update`, which is the file into which you should have put all this code, and then try to push a commit with a non-compliant message, you get something like this | `git push -f origin master` |

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error: hooks/update exited with error code 1` | There are a couple of interesting things here. |
| `! [remote rejected] master -> master (hook declined)` | You’ll see a remote rejected message for each reference that your hook declined, and it tells you that it was declined specifically because of a hook failure. |


## Related skills

- `git-hooks` - Git Hooks
- `git-configuration` - Git Configuration
- `git-as-a-client` - Git as a Client
- `git-distributed-git-contributing-to-a-project` - Contributing to a Project

## Source

"Pro Git", pages 363-372. Sections: An Example Git-Enforced Policy; An Example Git-Enforced Policy > Server-Side Hook; An Example Git-Enforced Policy > Client-Side Hooks.
