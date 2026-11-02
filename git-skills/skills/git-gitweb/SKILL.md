---
name: git-gitweb
description: "GitWeb playbook extracted from \"Pro Git\". Git comes with a CGI script called GitWeb that is sometimes used for this. Use when the user asks about gitweb, simple web-based visualizer, basic read, write and read-only, read-only access, cgi script, gitweb; or mentions git instaweb --httpd, git instaweb --httpd --stop, git clone, cd, make, cp -Rf."
---

# GitWeb

Git comes with a CGI script called GitWeb that is sometimes used for this.

_Built from "Pro Git" (pages 125-127) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **gitweb** (simple web-based visualizer, basic read, write and read-only, read-only access, cgi script).
- The user wants to run or understand `git instaweb --httpd`.
- The user wants to run or understand `git instaweb --httpd --stop`.
- The user wants to run or understand `git clone`.
- The user wants to run or understand `cd`.
- If you want to check out what GitWeb would look like for your project, Git comes with a command to fire up a temporary instance if you have a lightweight web server on your system like `lighttpd` or `webrick`.

## When NOT to use

- For smart http, use the `git-smart-http` skill instead.
- For installing git, use the `git-installing-git` skill instead.
- For getting git on a server, use the `git-getting-git-on-a-server` skill instead.

## Key concepts

- If you want to check out what GitWeb would look like for your project, Git comes with a command to fire up a temporary instance if you have a lightweight web server on your system like `lighttpd` or `webrick`.
- On Linux machines, `lighttpd` is often installed, so you may be able to get it to run by typing `git instaweb` in your project directory.
- To start `instaweb` with a non-lighttpd handler, you can run it with the `--httpd` option.
- That starts up an HTTPD server on port 1234 and then automatically starts a web browser that opens on that page.
- If you want to run the web interface on a server all the time for your team or for an open source project you’re hosting, you’ll need to set up the CGI script to be served by your normal web server.
- Some Linux distributions have a `gitweb` package that you may be able to install via `apt` or `dnf`, so you may want to try that first.
- We’ll walk through installing GitWeb manually very quickly.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### GitWeb

**Goal:** If you want to check out what GitWeb would look like for your project, Git comes with a command to fire up a temporary instance if you have a lightweight web server on your system like `lighttpd` or `webrick`.

**Steps:**

1. To start `instaweb` with a non-lighttpd handler, you can run it with the `--httpd` option.
   ```bash
   git instaweb --httpd=webrick
   ```
   Expected output (excerpt):
   ```text
   [2009-02-21 10:02:21] INFO  WEBrick 1.3.1
   ```
2. Run:
   ```text
   [2009-02-21 10:02:21] INFO  ruby 1.8.6 (2008-03-03) [universal-darwin9.0]
   ```
3. When you’re done and want to shut down the server, you can run the same command with the `--stop` option:
   ```bash
   git instaweb --httpd=webrick --stop
   ```
4. First, you need to get the Git source code, which GitWeb comes with, and generate the custom CGI script:
   ```bash
   git clone https://git.kernel.org/pub/scm/git/git.git
   cd git/
   make GITWEB_PROJECTROOT="/srv/git" prefix=/usr gitweb
   sudo cp -Rf gitweb /var/www/
   ```
   Expected output (excerpt):
   ```text
       SUBDIR gitweb
       SUBDIR ../
   make[2]: `GIT-VERSION-FILE' is up to date.
       GEN gitweb.cgi
   ```
5. Now, you need to make Apache use CGI for that script, for which you can add a VirtualHost:
   ```text
   <VirtualHost *:80>
       ServerName gitserver
       DocumentRoot /var/www/gitweb
       <Directory /var/www/gitweb>
           Options +ExecCGI +FollowSymLinks +SymLinksIfOwnerMatch
           AllowOverride All
           order allow,deny
           Allow from all
           AddHandler cgi-script cgi
           DirectoryIndex gitweb.cgi
       </Directory>
   </VirtualHost>
   ```

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `git instaweb --httpd` | To start `instaweb` with a non-lighttpd handler, you can run it with the `--httpd` option. | `git instaweb --httpd=webrick` |
| `git instaweb --httpd --stop` | When you’re done and want to shut down the server, you can run the same command with the `--stop` option | `git instaweb --httpd=webrick --stop` |
| `git clone` | First, you need to get the Git source code, which GitWeb comes with, and generate the custom CGI script | `git clone https://git.kernel.org/pub/scm/git/git.git` |
| `make` | Now, you need to make Apache use CGI for that script, for which you can add a VirtualHost | `make GITWEB_PROJECTROOT="/srv/git" prefix=/usr gitweb` |

## Related skills

- `git-smart-http` - Smart HTTP
- `git-installing-git` - Installing Git
- `git-getting-git-on-a-server` - Getting Git on a Server
- `git-setting-up-the-server` - Setting Up the Server

## Source

"Pro Git", pages 125-127. Sections: GitWeb.
