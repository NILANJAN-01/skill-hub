---
name: git-smart-http
description: "Serve git over HTTP(S) with git-http-backend and authenticated push. Use when you need to host a repo over HTTP."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Smart HTTP"
  category: git-collaboration
  source: "Pro Git, 2nd edition"
  pages: "123-125"
---

# Smart HTTP

Setting up Smart HTTP is basically just enabling a CGI script that is provided with Git called `git-http-backend` on the server.

_Built from "Pro Git" (pages 123-125) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **smart http** (access through ssh, cgi script, web server, http url, smart http).
- The user wants to run or understand `apt-get install`.
- The user wants to run or understand `a2enmod cgi`.
- The user wants to run or understand `chgrp -R`.
- The user wants to run or understand `htpasswd -c`.

## When NOT to use

- For gitweb, use the `git-gitweb` skill instead.
- For the protocols, use the `git-the-protocols` skill instead.
- For git daemon, use the `git-daemon` skill instead.

## Key concepts

- This CGI will read the path and headers sent by a `git fetch` or `git push` to an HTTP URL and determine if the client can communicate over HTTP (which is true for any client since version 1.6.6).
- If the CGI sees that the client is smart, it will communicate smartly with it; otherwise it will fall back to the dumb behavior (so it is backward compatible for reads with older clients).
- We’ll set this up with Apache as the CGI server.
- If you leave out `GIT_HTTP_EXPORT_ALL` environment variable, then Git will only serve to unauthenticated clients the repositories with the `git-daemon-export-ok` file in them, just like the Git daemon did.
- We don’t want to go too far down the rabbit hole of Apache configuration specifics, since you could well be using a different server or have different authentication needs.
- The idea is that Git comes with a CGI called `git-http-backend` that when invoked will do all the negotiation to send and receive data over HTTP.
- It does not implement any authentication itself, but that can easily be controlled at the layer of the web server that invokes it.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Smart HTTP

**Goal:** Setting up Smart HTTP is basically just enabling a CGI script that is provided with Git called `git-http-backend` on the server.

**Steps:**

1. If you don’t have Apache setup, you can do so on a Linux box with something like this:
   ```bash
   sudo apt-get install apache2 apache2-utils
   ```
2. Run:
   ```bash
   a2enmod cgi alias env
   ```
3. You’ll also need to set the Unix user group of the `/srv/git` directories to `www-data` so your web server can read- and write-access the repositories, because the Apache instance running the CGI script will (by default) be running as that user:
   ```bash
   chgrp -R www-data /srv/git
   ```
4. Next we need to add some things to the Apache configuration to run the `git-http-backend` as the handler for anything coming into the `/git` path of your web server.
   ```text
   SetEnv GIT_PROJECT_ROOT /srv/git
   SetEnv GIT_HTTP_EXPORT_ALL
   ScriptAlias /git/ /usr/lib/git-core/git-http-backend/
   ```
5. Finally you’ll want to tell Apache to allow requests to `git-http-backend` and make writes be authenticated somehow, possibly with an Auth block like this:
   ```text
   <Files "git-http-backend">
       AuthType Basic
       AuthName "Git Access"
       AuthUserFile /srv/git/.htpasswd
       Require expr !(%{QUERY_STRING} -strmatch '*service=git-receive-pack*' ||
   %{REQUEST_URI} =~ m#/git-receive-pack$#)
       Require valid-user
   </Files>
   ```
6. Here is an example of adding a “schacon” user to the file:
   ```bash
   htpasswd -c /srv/git/.htpasswd schacon
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `apt-get install` | If you don’t have Apache setup, you can do so on a Linux box with something like this | `sudo apt-get install apache2 apache2-utils` |
| `a2enmod cgi` | If you don’t have Apache setup, you can do so on a Linux box with something like this | `a2enmod cgi alias env` |
| `chgrp -R` | You’ll also need to set the Unix user group of the `/srv/git` directories to `www-data` so your web server can read- and write-access the repositories, because the Apache instance running the CGI script will (by default) be running as that user | `chgrp -R www-data /srv/git` |
| `htpasswd -c` | Here is an example of adding a “schacon” user to the file | `htpasswd -c /srv/git/.htpasswd schacon` |

## Troubleshooting

- **Note:** For more information on configuring authentication in Apache, check out the Apache docs here: https://httpd.apache.org/docs/current/howto/auth.html.

## Related skills

- `git-gitweb` - GitWeb
- `git-the-protocols` - The Protocols
- `git-daemon` - Git Daemon
- `git-getting-git-on-a-server` - Getting Git on a Server

## Source

"Pro Git", pages 123-125. Sections: Smart HTTP.
