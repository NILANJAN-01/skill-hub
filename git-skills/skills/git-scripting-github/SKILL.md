---
name: git-scripting-github
description: "Scripting GitHub playbook extracted from \"Pro Git\". The Hooks and Services section of GitHub repository administration is the easiest way to have Use when the user asks about scripting github, web hook, web service, add service, service integration, continuous integration services, email; or mentions curl, curl -H."
---

# Scripting GitHub

The Hooks and Services section of GitHub repository administration is the easiest way to have

_Built from "Pro Git" (pages 214-223) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **scripting github** (web hook, web service, add service, service integration, continuous integration services).
- The user wants to run or understand `curl`.
- The user wants to run or understand `curl -H`.
- The Hooks and Services section of GitHub repository administration is the easiest way to have
- This is where the GitHub API comes in handy.
- You can now use this to authenticate in your script instead of using a username and password.

## When NOT to use

- For contributing to a project, use the `git-github-contributing-to-a-project` skill instead.
- For maintaining a project, use the `git-github-maintaining-a-project` skill instead.
- For git hooks, use the `git-hooks` skill instead.

## Key concepts

- If there is a system you are using that you would like to integrate with GitHub, you should check here to see if there is an existing service integration available.
- GitHub repository hooks are pretty simple.
- Generally the way this works is you can setup a small web service to listen for a GitHub hook payload and then do something with the data when it is received.
- There are a few options for which events you want GitHub to send you a payload for — the default is to only get a payload for the `push` event, when someone pushes new code to any branch of your repository.
- For more information on how to write webhooks and all the different event types you can listen for, go to the GitHub Developer documentation at https://docs.github.com/en/webhooks-and-events/ webhooks/about-webhooks.
- There are tons of endpoints like this to get information about organizations, projects, issues, commits — just about anything you can publicly see on GitHub.
- If someone opens a new Pull Request on GitHub and this hook is set up, you may see something like

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

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
   # ... (full listing in references)
   ```

### Basic Usage

**Goal:** There are tons of endpoints like this to get information about organizations, projects, issues, commits — just about anything you can publicly see on GitHub.

**Steps:**

1. For example, if we want to know more about a user named “schacon”, we can run something like this:
   ```bash
   curl https://api.github.com/users/schacon
   ```
   Expected output (excerpt):
   ```text
   {
     "login": "schacon",
     "id": 70,
     "avatar_url": "https://avatars.githubusercontent.com/u/70",
   ```
2. You can even use the API to render arbitrary Markdown or find a `.gitignore` template.
   ```bash
   curl https://api.github.com/gitignore/templates/Java
   ```
   Expected output (excerpt):
   ```text
   {
     "name": "Java",
     "source": "*.class
   # Mobile Tools for Java (J2ME)
   ```

### Commenting on an Issue

**Goal:** You can now use this to authenticate in your script instead of using a username and password.

**Steps:**

1. To do so we have to do an HTTP POST request to `repos/<user>/<repo>/issues/<num>/comments` with the token we just generated as an Authorization header.
   ```bash
   curl -H "Content-Type: application/json" \
   -H "Authorization: token TOKEN" \
   --data '{"body":"A new comment, :+1:"}' \
   https://api.github.com/repos/schacon/blink/issues/6/comments
   ```
2. Run:
   ```text
   {
     "id": 58322100,
     "html_url": "https://github.com/schacon/blink/issues/6#issuecomment-58322100",
     ...
     "user": {
       "login": "tonychacon",
       "id": 7874698,
       "avatar_url": "https://avatars.githubusercontent.com/u/7874698?v=2",
       "type": "User",
     },
     "created_at": "2014-10-08T07:48:19Z",
     "updated_at": "2014-10-08T07:48:19Z",
     "body": "A new comment, :+1:"
   }
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
   # ... (full listing in references)
   ```

More procedures in [references/procedures.md](references/procedures.md):

- Services and Hooks
- Changing the Status of a Pull Request

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `curl` | Though we’ve been doing nearly everything through `curl` and simple HTTP requests in these examples, several open-source libraries exist that make this API available in a more idiomatic way. | `curl https://api.github.com/users/schacon` |
| `curl -H -H` | To do so we have to do an HTTP POST request to `repos/<user>/<repo>/issues/<num>/comments` with the token we just generated as an Authorization header. | `curl -H "Content-Type: application/json" \` |

## Decision guide

- If there is a system you are using that you would like to integrate with GitHub, you should check here to see if there is an existing service integration available.
- If you need something more specific or you want to integrate with a service or site that is not included in this list, you can instead use the more generic hooks system.
- You can now use this to authenticate in your script instead of using a username and password.

## Related skills

- `git-github-contributing-to-a-project` - Contributing to a Project
- `git-github-maintaining-a-project` - Maintaining a Project
- `git-hooks` - Git Hooks
- `git-libgit2` - Libgit2

## Source

"Pro Git", pages 214-223. Sections: Scripting GitHub; Scripting GitHub > Services and Hooks; Scripting GitHub > The GitHub API; Scripting GitHub > Basic Usage; Scripting GitHub > Commenting on an Issue; Scripting GitHub > Changing the Status of a Pull Request; Scripting GitHub > Octokit.
