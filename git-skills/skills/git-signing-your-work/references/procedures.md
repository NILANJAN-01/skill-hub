# More procedures: Signing Your Work

### Signing Tags

**Goal:** If you have a GPG private key set up, you can now use it to sign new tags.

**Steps:**

1. All you have to do is use `-s` instead of `-a`:
   ```bash
   git tag -s v1.5 -m 'my signed 1.5 tag'
   ```
   Expected output (excerpt):
   ```text
   You need a passphrase to unlock the secret key for
   user: "Ben Straub <ben@straub.cc>"
   2048-bit RSA key, ID 800430EB, created 2014-05-04
   ```
2. If you run `git show` on that tag, you can see your GPG signature attached to it:
   ```bash
   git show v1.5
   ```
   Expected output (excerpt):
   ```text
   tag v1.5
   Tagger: Ben Straub <ben@straub.cc>
   ```
3. Run:
   ```text
   Date:   Sat May 3 20:29:41 2014 -0700
   my signed 1.5 tag
   -----BEGIN PGP SIGNATURE-----
   Version: GnuPG v1
   iQEcBAABAgAGBQJTZbQlAAoJEF0+sviABDDrZbQH/09PfE51KPVPlanr6q1v4/Ut
   LQxfojUWiLQdg2ESJItkcuweYg+kc3HCyFejeDIBw9dpXt00rY26p05qrpnG+85b
   hM1/PswpPLuBSr+oCIDj5GMC2r2iEKsfv2fJbNW8iWAXVLoWZRF8B0MfqX/YTMbm
   ecorc4iXzQu7tupRihslbNkfvfciMnSDeSvzCpWAHl7h8Wj6hhqePmLm9lAYqnKp
   8S5B/1SSQuEAjRZgI4IexpZoeKGVDptPHxLLS38fozsyi0QyDyzEgJxcJQVMXxVi
   RUysgqjcpT8+iQM1PblGfHR4XAhuOqN5Fx06PSaFZhqvWFezJ28/CLyX5q+oIVk=
   =EFTF
   -----END PGP SIGNATURE-----
   commit ca82a6dff817ec66f44342007202690a93763949
   Author: Scott Chacon <schacon@gee-mail.com>
   Date:   Mon Mar 17 21:52:11 2008 -0700
       Change version number
   ```

**Verify:** run `git show v1.5` - expect something like:
```text
tag v1.5
Tagger: Ben Straub <ben@straub.cc>
```

### Signing Commits

**Goal:** In more recent versions of Git (v1.7.9 and above), you can now also sign individual commits.

**Steps:**

1. If you’re interested in signing commits directly instead of just the tags, all you need to do is add a `-S` to your `git commit` command.
   ```bash
   git commit -a -S -m 'Signed commit'
   ```
   Expected output (excerpt):
   ```text
   You need a passphrase to unlock the secret key for
   user: "Scott Chacon (Git signing key) <schacon@gmail.com>"
   2048-bit RSA key, ID 0A46826A, created 2014-06-04
   [master 5c3386c] Signed commit
   ```
2. To see and verify these signatures, there is also a `--show-signature` option to `git log`.
   ```bash
   git log --show-signature -1
   ```
   Expected output (excerpt):
   ```text
   commit 5c3386cf54bba0a33a32da706aa52bc0155503c2
   gpg: Signature made Wed Jun  4 19:49:17 2014 PDT using RSA key ID 0A46826A
   gpg: Good signature from "Scott Chacon (Git signing key) <schacon@gmail.com>"
   Author: Scott Chacon <schacon@gmail.com>
   ```
3. Additionally, you can configure `git log` to check any signatures it finds and list them in its output with the `%G?` format.
   ```bash
   git log --pretty="format:%h %G? %aN  %s"
   ```
   Expected output (excerpt):
   ```text
   5c3386c G Scott Chacon  Signed commit
   ca82a6d N Scott Chacon  Change the version number
   085bb3b N Scott Chacon  Remove unnecessary test code
   a11bef0 N Scott Chacon  Initial commit
   ```
4. If you use this option when merging a branch and it contains commits that are not signed and valid, the merge will not work.
   ```bash
   git merge --verify-signatures non-verify
   ```
5. Run:
   ```text
   fatal: Commit ab06180 does not have a GPG signature.
   ```
6. If the merge contains only valid signed commits, the merge command will show you all the signatures it has checked and then move forward with the merge.
   ```bash
   git merge --verify-signatures signed-branch
   ```
   Expected output (excerpt):
   ```text
   Commit 13ad65e has a good GPG signature by Scott Chacon (Git signing key)
   <schacon@gmail.com>
   Updating 5c3386c..13ad65e
   Fast-forward
   ```
7. The following example both verifies that every commit in the branch to be merged is signed and furthermore signs the resulting merge commit.
   ```bash
   git merge --verify-signatures -S  signed-branch
   ```
   Expected output (excerpt):
   ```text
   Commit 13ad65e has a good GPG signature by Scott Chacon (Git signing key)
   <schacon@gmail.com>
   You need a passphrase to unlock the secret key for
   user: "Scott Chacon (Git signing key) <schacon@gmail.com>"
   ```

**Verify:** run `git log --pretty="format:%h %G? %aN  %s"` - expect something like:
```text
5c3386c G Scott Chacon  Signed commit
ca82a6d N Scott Chacon  Change the version number
085bb3b N Scott Chacon  Remove unnecessary test code
a11bef0 N Scott Chacon  Initial commit
```
