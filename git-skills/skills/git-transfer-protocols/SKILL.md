---
name: git-transfer-protocols
description: "Transfer Protocols playbook extracted from \"Pro Git\". If you’re setting up a repository to be served read-only over HTTP, the dumb protocol is likely what will be used. Use when the user asks about transfer protocols, git checks, dumb protocol, commit object, head, remote, master; or mentions ssh -x, git clone, git cat-file -p."
---

# Transfer Protocols

If you’re setting up a repository to be served read-only over HTTP, the dumb protocol is likely what will be used.

_Built from "Pro Git" (pages 441-446) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **transfer protocols** (git checks, dumb protocol, commit object, head, remote).
- The user wants to run or understand `ssh -x`.
- The user wants to run or understand `git clone`.
- The user wants to run or understand `git cat-file -p`.

## When NOT to use

- For the protocols, use the `git-the-protocols` skill instead.
- For bundling, use the `git-bundling` skill instead.
- For git references, use the `git-references` skill instead.

## Key concepts

- This protocol is called “dumb” because it requires no Git-specific code on the server side during the transport process; the fetch process is a series of HTTP `GET` requests, where the client can assume the layout of the Git repository on the server.
- If this comes back with a list of alternate URLs, Git checks for loose files and packfiles there – this is a nice mechanism for projects that are forks of one another to share objects on disk.
- The dumb protocol is simple but a bit inefficient, and it can’t handle writing of data from the client to the server.
- The smart protocol is a more common method of transferring data, but it requires a process on the remote end that is intelligent about Git – it can read local data, figure out what the client has and needs, and generate a custom packfile for it.
- To upload data to a remote process, Git uses the `send-pack` and `receive-pack` processes.
- The `send-pack` process runs on the client and connects to a `receive-pack` process on the remote side.
- The client initiates a `fetch-pack` process that connects to an `upload-pack` process on the remote side to negotiate what data will be transferred down.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### The Dumb Protocol

**Goal:** This protocol is called “dumb” because it requires no Git-specific code on the server side during the transport process; the fetch process is a series of HTTP `GET` requests, where the client can assume the layout of the Git repository on the server.

**Steps:**

1. Let’s follow the `http-fetch` process for the simplegit library:
   ```bash
   git clone http://server/simplegit-progit.git
   ```
2. HTTP transport to work properly:
   ```text
   => GET info/refs
   ca82a6dff817ec66f44342007202690a93763949     refs/heads/master
   ```
3. Next, you look for what the HEAD reference is so you know what to check out when you’re finished:
   ```text
   => GET HEAD
   ref: refs/heads/master
   ```
4. Because your starting point is the `ca82a6` commit object you saw in the `info/refs` file, you start by fetching that:
   ```text
   => GET objects/ca/82a6dff817ec66f44342007202690a93763949
   (179 bytes of binary data)
   ```
5. You can zlib-uncompress it, strip off the header, and look at the commit content:
   ```bash
   git cat-file -p ca82a6dff817ec66f44342007202690a93763949
   ```
   Expected output (excerpt):
   ```text
   tree cfda3bf379e4f8dba8717dee55aab78aef7f4daf
   parent 085bb3bcb608e1e8451d4b2432f8ecbe6306e7e7
   author Scott Chacon <schacon@gmail.com> 1205815931 -0700
   committer Scott Chacon <schacon@gmail.com> 1240030591 -0700
   ```
6. Next, you have two more objects to retrieve – `cfda3b`, which is the tree of content that the commit we just retrieved points to; and `085bb3`, which is the parent commit:
   ```text
   => GET objects/08/5bb3bcb608e1e8451d4b2432f8ecbe6306e7e7
   (179 bytes of data)
   ```

_5 more step(s) in references/procedures.md._

**Verify:** run `git cat-file -p ca82a6dff817ec66f44342007202690a93763949` - expect something like:
```text
tree cfda3bf379e4f8dba8717dee55aab78aef7f4daf
parent 085bb3bcb608e1e8451d4b2432f8ecbe6306e7e7
author Scott Chacon <schacon@gmail.com> 1205815931 -0700
committer Scott Chacon <schacon@gmail.com> 1240030591 -0700
Change version number
```

### The Smart Protocol

**Goal:** The smart protocol is a more common method of transferring data, but it requires a process on the remote end that is intelligent about Git – it can read local data, figure out what the client has and needs, and generate a custom packfile for it.

**Steps:**

1. It tries to run a command on the remote server via an SSH call that looks something like this:
   ```bash
   ssh -x git@server "git-receive-pack 'simplegit-progit.git'"
   ```
   Expected output (excerpt):
   ```text
   00a5ca82a6dff817ec66f4437202690a93763949 refs/heads/master□report-status \
       delete-refs side-band-64k quiet ofs-delta \
       agent=git/2:2.1.1+github-607-gfba4028 delete-refs
   0000
   ```
2. For instance, if you’re updating the `master` branch and adding an `experiment` branch, the `send-pack` response may look something like this:
   ```text
   0076ca82a6dff817ec66f44342007202690a93763949 15027957951b64cf874c3557a0f3547bd83b3ff6
   \
       refs/heads/master report-status
   006c0000000000000000000000000000000000000000 cdfdb42577e2506715f8cfeacdbabc092bf63e8d
   \
       refs/heads/experiment
   0000
   ```
3. Finally, the server responds with a success (or failure) indication:
   ```text
   000eunpack ok
   ```
4. The connection is initiated with this request:
   ```text
   => GET http://server/simplegit-progit.git/info/refs?service=git-receive-pack
   001f# service=git-receive-pack
   00ab6c5f0e45abd7832bf23074a333f739977c9e8188 refs/heads/master□report-status \
       delete-refs side-band-64k quiet ofs-delta \
       agent=git/2:2.1.1~vmg-bitmaps-bugaloo-608-g116744e
   0000
   ```
5. The client then makes another request, this time a `POST`, with the data that `send-pack` provides.
   ```text
   => POST http://server/simplegit-progit.git/git-receive-pack
   ```
6. If you’re doing the fetch over SSH, `fetch-pack` runs something like this:
   ```bash
   ssh -x git@server "git-upload-pack 'simplegit-progit.git'"
   ```

_5 more step(s) in references/procedures.md._

More procedures in [references/procedures.md](references/procedures.md):

- The Dumb Protocol
- The Smart Protocol

## Command reference

| Command | What it does (from source) | Example |
|---|---|---|
| `ssh -x` | It tries to run a command on the remote server via an SSH call that looks something like this | `ssh -x git@server "git-upload-pack 'simplegit-progit.git'"` |
| `git clone` | Let’s follow the `http-fetch` process for the simplegit library | `git clone http://server/simplegit-progit.git` |
| `git cat-file -p` | You can zlib-uncompress it, strip off the header, and look at the commit content | `git cat-file -p ca82a6dff817ec66f44342007202690a93763949` |

## Troubleshooting

- **Note:** The dumb protocol is fairly rarely used these days. It’s difficult to secure or make private, so most Git hosts (both cloud-based and on-premises) will refuse to use it. It’s generally advised to use the smart protocol, which we describe a bit further on.

## Related skills

- `git-the-protocols` - The Protocols
- `git-bundling` - Bundling
- `git-references` - Git References
- `git-as-a-client` - Git as a Client

## Source

"Pro Git", pages 441-446. Sections: Transfer Protocols; Transfer Protocols > The Dumb Protocol; Transfer Protocols > The Smart Protocol; Transfer Protocols > Protocols Summary.
