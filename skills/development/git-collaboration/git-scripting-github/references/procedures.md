# More procedures: Scripting GitHub

### Services and Hooks

**Goal:** The Hooks and Services section of GitHub repository administration is the easiest way to have

**Steps:**

1. We could fairly easily do that with code like this:
   ```ruby
   require 'sinatra'
   require 'json'
   require 'mail'
   post '/payload' do
     push = JSON.parse(request.body.read) # parse the JSON
     # gather the data we're looking for
     pusher = push["pusher"]["name"]
     branch = push["ref"]
     # get a list of all the files touched
     files = push["commits"].map do |commit|
       commit['added'] + commit['modified'] + commit['removed']
     end
     files = files.flatten.uniq
     # check for our criteria
     if pusher == 'schacon' &&
        branch == 'ref/heads/special-branch' &&
        files.include?('special-file.txt')
       Mail.deliver do
         from     'tchacon@example.com'
         to       'tchacon@example.com'
         subject  'Scott Changed the File'
         body     "ALARM"
       end
     end
   end
   ```

### Changing the Status of a Pull Request

**Goal:** If someone opens a new Pull Request on GitHub and this hook is set up, you may see something like

**Steps:**

1. Let’s say you set up a webhook on your repository that hits a small web service that checks for a `Signed-off-by` string in the commit message.
   ```text
   require 'httparty'
   require 'sinatra'
   require 'json'
   ```
2. Run:
   ```ruby
   post '/payload' do
     push = JSON.parse(request.body.read) # parse the JSON
     repo_name = push['repository']['full_name']
     # look through each commit message
     push["commits"].each do |commit|
       # look for a Signed-off-by string
       if /Signed-off-by/.match commit['message']
         state = 'success'
         description = 'Successfully signed off!'
       else
         state = 'failure'
         description = 'No signoff found.'
       end
       # post status to GitHub
       sha = commit["id"]
       status_url = "https://api.github.com/repos/#{repo_name}/statuses/#{sha}"
       status = {
         "state"       => state,
         "description" => description,
         "target_url"  => "http://example.com/how-to-signoff",
         "context"     => "validate/signoff"
       }
       HTTParty.post(status_url,
         :body => status.to_json,
         :headers => {
           'Content-Type'  => 'application/json',
           'User-Agent'    => 'tonychacon/signoff',
           'Authorization' => "token #{ENV['TOKEN']}" }
       )
     end
   end
   ```
