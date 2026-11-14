# Security policy

Skills can include scripts that run on a user's machine, and `tools/install.py` writes into agents' skill folders, so security reports matter here.

## Report a vulnerability

Use GitHub's **private vulnerability reporting**: open the repository's **Security** tab and choose **Report a vulnerability**. Please do not open a public issue for a security problem.

Useful things to include: the skill or tool affected, the version or commit, and the steps to reproduce.

## In scope

- `tools/install.py` writing outside the intended skill folders, following links, or installing without confirmation.
- Path traversal or unsafe file reads in `mcp-server/` (it must stay read-only).
- A skill whose instructions or scripts delete data, exfiltrate data, or run destructive commands without asking the user first.
- Secrets or private data committed to the repository.

## Supported versions

Only the latest release and `main` receive fixes.
