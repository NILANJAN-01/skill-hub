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

This page is the short version: the safety rules, the commands and the fixes. Open [references/playbook.md](references/playbook.md) for the concepts, step-by-step procedures and decision guide, and [references/source-text.md](references/source-text.md) for the book text, only when a step needs more than this page.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Commands

- `apt-get install`: `sudo apt-get install apache2 apache2-utils`
- `a2enmod cgi`: `a2enmod cgi alias env`
- `chgrp -R`: `chgrp -R www-data /srv/git`
- `htpasswd -c`: `htpasswd -c /srv/git/.htpasswd schacon`

## Troubleshooting

- **Note:** For more information on configuring authentication in Apache, check out the Apache docs here: https://httpd.apache.org/docs/current/howto/auth.html.

## Related skills

- `git-gitweb` - GitWeb
- `git-the-protocols` - The Protocols
- `git-daemon` - Git Daemon
- `git-getting-git-on-a-server` - Getting Git on a Server

_Source: "Pro Git" by Scott Chacon and Ben Straub, pages 123-125, CC BY-NC-SA 3.0._
