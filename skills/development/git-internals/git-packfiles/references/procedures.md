# More procedures: Packfiles

### Packfiles

**Goal:** The packfile is a single file containing the contents of all the objects that were removed from your filesystem.

**Steps:**

1. If you followed all of the instructions in the example from the previous section, you should now have a test Git repository with 11 objects — four blobs, three trees, three commits, and one tag:
   ```bash
   find .git/objects -type f
   ```
   Expected output (excerpt):
   ```text
   .git/objects/01/55eb4229851634a0f03eb265b69f5a2d56f341 # tree 2
   .git/objects/1a/410efbd13591db07496601ebc7a059dd55cfe9 # commit 3
   .git/objects/1f/7a7a472abf3dd9643fd615f6da379c4acb3e3a # test.txt v2
   .git/objects/3c/4e9cd789d88d8d89c1073707c3585e41b0e614 # tree 3
   ```
2. To demonstrate, we’ll add the `repo.rb` file from the Grit library — this is about a 22K source code file:
   ```bash
   curl https://raw.githubusercontent.com/mojombo/grit/master/lib/grit/repo.rb >
   git checkout master
   git add repo.rb
   git commit -m 'Create repo.rb'
   ```
   Expected output (excerpt):
   ```text
   repo.rb
   [master 484a592] Create repo.rb
    3 files changed, 709 insertions(+), 2 deletions(-)
    delete mode 100644 bak/test.txt
   ```
3. If you look at the resulting tree, you can see the SHA-1 value that was calculated for your new `repo.rb` blob object:
   ```bash
   git cat-file -p master^{tree}
   ```
   Expected output (excerpt):
   ```text
   100644 blob fa49b077972391ad58037050f2a75f74e3671e92      new.txt
   100644 blob 033b4468fa6b2a9547a70d88d1bbe8bf3f9ed0d5      repo.rb
   100644 blob e3f094f522629ae358806b17daf78246c27c007b      test.txt
   ```
4. You can then use `git cat-file` to see how large that object is:
   ```bash
   git cat-file -s 033b4468fa6b2a9547a70d88d1bbe8bf3f9ed0d5
   ```
   Expected output (excerpt):
   ```text
   22044
   ```
5. At this point, modify that file a little, and see what happens:
   ```bash
   echo '# testing' >> repo.rb
   git commit -am 'Modify repo.rb a bit'
   ```
   Expected output (excerpt):
   ```text
   [master 2431da6] Modify repo.rb a bit
    1 file changed, 1 insertion(+)
   ```
6. Check the tree created by that last commit, and you see something interesting:
   ```bash
   git cat-file -p master^{tree}
   ```
   Expected output (excerpt):
   ```text
   100644 blob fa49b077972391ad58037050f2a75f74e3671e92      new.txt
   100644 blob b042a60ef7dff760008df33cee372b945b6e884e      repo.rb
   100644 blob e3f094f522629ae358806b17daf78246c27c007b      test.txt
   ```
7. The blob is now a different blob, which means that although you added only a single line to the end of a 400-line file, Git stored that new content as a completely new object:
   ```bash
   git cat-file -s b042a60ef7dff760008df33cee372b945b6e884e
   ```
   Expected output (excerpt):
   ```text
   22054
   ```
8. To see what happens, you can manually ask Git to pack up the objects by calling the `git gc` command:
   ```bash
   git gc
   ```
9. Run:
   ```text
   Counting objects: 18, done.
   Delta compression using up to 8 threads.
   Compressing objects: 100% (14/14), done.
   Writing objects: 100% (18/18), done.
   Total 18 (delta 3), reused 0 (delta 0)
   ```
10. If you look in your `objects` directory, you’ll find that most of your objects are gone, and a new pair of files has appeared:
   ```bash
   find .git/objects -type f
   ```
   Expected output (excerpt):
   ```text
   .git/objects/bd/9dbf5aae1a3862dd1526723246b20206e5fc37
   .git/objects/d6/70460b4b4aece5915caf5c68d12f560a9fe3e4
   .git/objects/info/packs
   .git/objects/pack/pack-978e03944f5c581011e6998cd0e9e30000905586.idx
   ```
11. The `git verify-pack` plumbing command allows you to see what was packed up:
   ```bash
   git verify-pack -v .git/objects/pack/pack-
   ```
   Expected output (excerpt):
   ```text
   978e03944f5c581011e6998cd0e9e30000905586.idx
   2431da676938450a4d72e260db3bf7b0f587bbc1 commit 223 155 12
   69bcdaff5328278ab1c0812ce0e07fa7d26a96d7 commit 214 152 167
   80d02664cb23ed55b226516648c7ad5d0a3deb90 commit 214 145 319
   ```
12. Run:
   ```text
   0155eb4229851634a0f03eb265b69f5a2d56f341 tree   71 76 1350
   83baae61804e65cc73a7201a7252750c76066a30 blob   10 19 1426
   fa49b077972391ad58037050f2a75f74e3671e92 blob   9 18 1445
   b042a60ef7dff760008df33cee372b945b6e884e blob   22054 5799 1463
   033b4468fa6b2a9547a70d88d1bbe8bf3f9ed0d5 blob   9 20 7262 1 \
     b042a60ef7dff760008df33cee372b945b6e884e
   1f7a7a472abf3dd9643fd615f6da379c4acb3e3a blob   10 19 7282
   non delta: 15 objects
   chain length = 1: 3 objects
   .git/objects/pack/pack-978e03944f5c581011e6998cd0e9e30000905586.pack: ok
   ```

**Verify:** run `git cat-file -s b042a60ef7dff760008df33cee372b945b6e884e` - expect something like:
```text
22054
```
