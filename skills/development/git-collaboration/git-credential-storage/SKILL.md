---
name: git-credential-storage
description: "Stop git asking for passwords: credential helpers and Git Credential Manager. Use when git prompts on every push or pull."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Credential Storage"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "336-341"
---

# Credential Storage

This means that until you change your password for the Git host, you won’t ever have to type in your credentials again.

_Built from "Pro Git" (pages 336-341) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **credential storage** (git credential, ssh transport, credential helper, file, securely transfer data).
- The user wants to run or understand `git credential`.
- The user wants to run or understand `git credential-store --file`.
- The user wants to run or understand `git credential-read-only --file`.
- The user wants to run or understand `git config --global --file`.

## When NOT to use

- •The “store” mode saves the credentials to a plain-text file on disk, and they never expire.
- This method stores the credentials on disk, and they never expire, but they’re encrypted with the same system that stores HTTPS certificates and Safari auto-fills.
- These are stored in a shared directory, but you don’t want to copy them to your own credential store, because they change often.
- For git configuration, use the `git-configuration` skill instead.
- For the protocols, use the `git-the-protocols` skill instead.
- For git objects, use the `git-objects` skill instead.

## Key concepts

- Fortunately, Git has a credentials system that can help with this.
- The “store” helper can take a `--file <path>` argument, which customizes where the plain-text file is saved (the default is `~/.git-credentials`).
- Git’s root command for the credential-helper system is `git credential`, which takes a command as an argument, and then more input through stdin.
- •`store` is a request to save a set of credentials in this helper’s memory.
- `③git-credential-store` replies with the username and password we stored above.
- Given that `git-credential-store` and friends are separate programs from Git, it’s not much of a leap to realize that any program can be a Git credential helper.
- 2.The file format of the shared-credential file is the same as that used by `git-credential-store`.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Credential Storage

**Goal:** This means that until you change your password for the Git host, you won’t ever have to type in your credentials again.

**Steps:**

1. You can choose one of these methods by setting a Git configuration value:
   ```bash
   git config --global credential.helper cache
   ```
2. helper with a custom file name:
   ```bash
   git config --global credential.helper 'store --file ~/.my-credentials'
   ```
3. Here’s what a `.gitconfig` would look like if you had a credentials file on a thumb drive, but wanted to use the in-memory cache to save some typing if the drive isn’t plugged in:
   ```ini
   [credential]
       helper = store --file /mnt/thumbdrive/.git-credentials
       helper = cache --timeout 30000
   ```

### Under the Hood

**Goal:** •`store` is a request to save a set of credentials in this helper’s memory.

**Steps:**

1. command, which is invoked when Git is trying to find credentials for a host:
   ```bash
   git credential fill ①
   git credential fill ⑤
   ```
   Expected output (excerpt):
   ```text
   protocol=https ②
   host=mygithost
   ③
   protocol=https ④
   ```
2. Here’s the same example from above, but skipping `git-credential` and going straight for `git-credential-store`:
   ```bash
   git credential-store --file ~/git.store store ①
   git credential-store --file ~/git.store get ②
   ```
   Expected output (excerpt):
   ```text
   protocol=https
   host=mygithost
   username=bob
   password=s3cre7
   ```
3. Run:
   ```text
   password=s3cre7
   ```
4. Here’s what the `~/git.store` file looks like:
   ```text
   https://bob:s3cre7@mygithost
   ```

### A Custom Credential Cache

**Goal:** 2.The file format of the shared-credential file is the same as that used by `git-credential-store`.

**Steps:**

1. Here’s the full source code of our new credential helper:
   ```ruby
   #!/usr/bin/env ruby
   require 'optparse'
   path = File.expand_path '~/.git-credentials' ①
   OptionParser.new do |opts|
       opts.banner = 'USAGE: git-credential-read-only [options] <action>'
       opts.on('-f', '--file PATH', 'Specify path for backing store') do |argpath|
           path = File.expand_path argpath
       end
   end.parse!
   ```
2. Run:
   ```ruby
   exit(0) unless ARGV[0].downcase == 'get' ②
   exit(0) unless File.exist? path
   known = {} ③
   while line = STDIN.gets
       break if line.strip == ''
       k,v = line.strip.split '=', 2
       known[k] = v
   end
   File.readlines(path).each do |fileline| ④
       prot,user,pass,host = fileline.scan(/^(.*?):\/\/(.*?):(.*?)@(.*)$/).first
       if prot == known['protocol'] and host == known['host'] and user ==
   known['username'] then
           puts "protocol=#{prot}"
           puts "host=#{host}"
           puts "username=#{user}"
   # ... (full listing in references)
   ```
3. Here’s what an interactive session looks like:
   ```bash
   git credential-read-only --file=/mnt/shared/creds get
   ```
   Expected output (excerpt):
   ```text
   protocol=https
   host=mygithost
   username=bob
   protocol=https
   ```
4. Since its name starts with “git-”, we can use the simple syntax for the configuration value:
   ```bash
   git config --global credential.helper 'read-only --file /mnt/shared/creds'
   ```

More procedures in [references/procedures.md](references/procedures.md):

- A Custom Credential Cache

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git config --global --file` | helper with a custom file name | `git config --global credential.helper 'store --file ~/.my-credentials'` |
| `git credential` | •If you’re using Windows, you can enable the Git Credential Manager feature when installing | `git credential fill ①` |
| `git credential-store --file` | Here’s the same example from above, but skipping `git-credential` and going straight for `git-credential-store` | `git credential-store --file ~/git.store get ②` |
| `git config --global` | You can choose one of these methods by setting a Git configuration value | `git config --global credential.helper cache` |
| `git credential-read-only --file` | Here’s what an interactive session looks like | `git credential-read-only --file=/mnt/shared/creds get` |

## Decision guide

- If the helper doesn’t know anything useful, it can simply exit with no output, but if it does know, it should augment the provided information with the information it has stored.

## Related skills

- `git-configuration` - Git Configuration
- `git-the-protocols` - The Protocols
- `git-objects` - Git Objects
- `git-environment-variables` - Environment Variables

## Source

"Pro Git", pages 336-341. Sections: Credential Storage; Credential Storage > Under the Hood; Credential Storage > A Custom Credential Cache.
