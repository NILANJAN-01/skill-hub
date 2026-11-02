# More procedures: Credential Storage

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
           puts "password=#{pass}"
           exit(0)
       end
   end
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
