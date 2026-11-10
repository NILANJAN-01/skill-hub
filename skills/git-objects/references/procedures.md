# More procedures: Git Objects

### Git Objects

**Goal:** As a demonstration, let’s look at the plumbing command `git hash-object`, which takes some data, stores it in your `.git/objects` directory (the object database), and gives you back the unique key that now refers to that data object.

**Steps:**

1. First, you initialize a new Git repository and verify that there is (predictably) nothing in the `objects` directory:
   ```bash
   git init test
   cd test
   find .git/objects
   find .git/objects -type f
   ```
   Expected output (excerpt):
   ```text
   Initialized empty Git repository in /tmp/test/.git/
   .git/objects
   .git/objects/info
   .git/objects/pack
   ```
2. Now, let’s use `git hash-object` to create a new data object and manually store it in your new Git database:
   ```bash
   echo 'test content' | git hash-object -w --stdin
   ```
3. Run:
   ```text
   d670460b4b4aece5915caf5c68d12f560a9fe3e4
   ```
4. Now you can see how Git has stored your data:
   ```bash
   find .git/objects -type f
   ```
   Expected output (excerpt):
   ```text
   .git/objects/d6/70460b4b4aece5915caf5c68d12f560a9fe3e4
   ```
5. Passing `-p` to `cat-file` instructs the command to first figure out the type of content, then display it appropriately:
   ```bash
   git cat-file -p d670460b4b4aece5915caf5c68d12f560a9fe3e4
   ```
   Expected output (excerpt):
   ```text
   test content
   ```
6. First, create a new file and save its contents in your database:
   ```bash
   echo 'version 1' > test.txt
   git hash-object -w test.txt
   ```
   Expected output (excerpt):
   ```text
   83baae61804e65cc73a7201a7252750c76066a30
   ```
7. Then, write some new content to the file, and save it again:
   ```bash
   echo 'version 2' > test.txt
   git hash-object -w test.txt
   ```
   Expected output (excerpt):
   ```text
   1f7a7a472abf3dd9643fd615f6da379c4acb3e3a
   ```
8. Your object database now contains both versions of this new file (as well as the first content you stored there):
   ```bash
   find .git/objects -type f
   ```
   Expected output (excerpt):
   ```text
   .git/objects/1f/7a7a472abf3dd9643fd615f6da379c4acb3e3a
   .git/objects/83/baae61804e65cc73a7201a7252750c76066a30
   .git/objects/d6/70460b4b4aece5915caf5c68d12f560a9fe3e4
   ```
9. At this point, you can delete your local copy of that `test.txt` file, then use Git to retrieve, from the object database, either the first version you saved:
   ```bash
   git cat-file -p 83baae61804e65cc73a7201a7252750c76066a30 > test.txt
   cat test.txt
   ```
   Expected output (excerpt):
   ```text
   version 1
   ```
10. or the second version:
   ```bash
   git cat-file -p 1f7a7a472abf3dd9643fd615f6da379c4acb3e3a > test.txt
   cat test.txt
   ```
   Expected output (excerpt):
   ```text
   version 2
   ```
11. You can have Git tell you the object type of any object in Git, given its SHA-1 key, with `git cat-file -t`:
   ```bash
   git cat-file -t 1f7a7a472abf3dd9643fd615f6da379c4acb3e3a
   ```
   Expected output (excerpt):
   ```text
   blob
   ```

**Verify:** run `git cat-file -t 1f7a7a472abf3dd9643fd615f6da379c4acb3e3a` - expect something like:
```text
blob
```

### Tree Objects

**Goal:** The next type of Git object we’ll examine is the tree, which solves the problem of storing the filename and also allows you to store a group of files together.

**Steps:**

1. For example, let’s say you have a project where the most-recent tree looks something like:
   ```bash
   git cat-file -p master^{tree}
   ```
   Expected output (excerpt):
   ```text
   100644 blob a906cb2a4a904a152e80877d4088654daad0c859      README
   100644 blob 8f94139338f9404f26296befa88755fc2598c289      Rakefile
   040000 tree 99f1a6d12cb4b6f19c8655fca46c3ecf317074e0      lib
   ```
2. Notice that the `lib` subdirectory isn’t a blob but a pointer to another tree:
   ```bash
   git cat-file -p 99f1a6d12cb4b6f19c8655fca46c3ecf317074e0
   ```
   Expected output (excerpt):
   ```text
   100644 blob 47c6340d6459e05787f644c2447d2595f5d3a54b      simplegit.rb
   ```
3. Then, you specify the mode, SHA-1, and filename:
   ```bash
   git update-index --add --cacheinfo 100644 \
   83baae61804e65cc73a7201a7252750c76066a30 test.txt
   ```
4. No `-w` option is needed — calling this command automatically creates a tree object from the state of the index if that tree doesn’t yet exist:
   ```bash
   git write-tree
   git cat-file -p d8329fc1cc938780ffdd9f94e0d364e0ea74f579
   ```
   Expected output (excerpt):
   ```text
   d8329fc1cc938780ffdd9f94e0d364e0ea74f579
   100644 blob 83baae61804e65cc73a7201a7252750c76066a30      test.txt
   ```
5. You can also verify that this is a tree object using the same `git cat-file` command you saw earlier:
   ```bash
   git cat-file -t d8329fc1cc938780ffdd9f94e0d364e0ea74f579
   ```
   Expected output (excerpt):
   ```text
   tree
   ```
6. You’ll now create a new tree with the second version of `test.txt` and a new file as well:
   ```bash
   echo 'new file' > new.txt
   git update-index --cacheinfo 100644 \
   1f7a7a472abf3dd9643fd615f6da379c4acb3e3a test.txt
   git update-index --add new.txt
   ```
7. Write out that tree (recording the state of the staging area or index to a tree object) and see what it looks like:
   ```bash
   git write-tree
   git cat-file -p 0155eb4229851634a0f03eb265b69f5a2d56f341
   ```
   Expected output (excerpt):
   ```text
   0155eb4229851634a0f03eb265b69f5a2d56f341
   100644 blob fa49b077972391ad58037050f2a75f74e3671e92      new.txt
   100644 blob 1f7a7a472abf3dd9643fd615f6da379c4acb3e3a      test.txt
   ```
8. In this case, you can read an existing tree into your staging area as a subtree by using the `--prefix` option with this command:
   ```bash
   git read-tree --prefix=bak d8329fc1cc938780ffdd9f94e0d364e0ea74f579
   git write-tree
   git cat-file -p 3c4e9cd789d88d8d89c1073707c3585e41b0e614
   ```
   Expected output (excerpt):
   ```text
   3c4e9cd789d88d8d89c1073707c3585e41b0e614
   040000 tree d8329fc1cc938780ffdd9f94e0d364e0ea74f579      bak
   100644 blob fa49b077972391ad58037050f2a75f74e3671e92      new.txt
   100644 blob 1f7a7a472abf3dd9643fd615f6da379c4acb3e3a      test.txt
   ```

**Verify:** run `git cat-file -t d8329fc1cc938780ffdd9f94e0d364e0ea74f579` - expect something like:
```text
tree
```

### Object Storage

**Goal:** We mentioned earlier that there is a header stored with every object you commit to your Git object database.

**Steps:**

1. You can start up interactive Ruby mode with the `irb` command:
   ```bash
   irb
   ```
   Expected output (excerpt):
   ```text
   >> content = "what is up, doc?"
   => "what is up, doc?"
   ```
2. To that first part of the header, Git adds a space followed by the size in bytes of the content, and adding a final null byte:
   ```text
   >> header = "blob #{content.bytesize}\0"
   => "blob 16\u0000"
   ```
3. You can calculate the SHA-1 value of a string in Ruby by including the SHA1 digest library with the `require` command and then calling `Digest::SHA1.hexdigest()` with the string:
   ```text
   >> store = header + content
   => "blob 16\u0000what is up, doc?"
   >> require 'digest/sha1'
   => true
   >> sha1 = Digest::SHA1.hexdigest(store)
   => "bd9dbf5aae1a3862dd1526723246b20206e5fc37"
   ```
4. Here we use `echo -n` to prevent adding a newline to the input.
   ```bash
   echo -n "what is up, doc?" | git hash-object --stdin
   ```
   Expected output (excerpt):
   ```text
   bd9dbf5aae1a3862dd1526723246b20206e5fc37
   ```
5. First, you need to require the library and then run `Zlib::Deflate.deflate()` on the content:
   ```text
   >> require 'zlib'
   => true
   >> zlib_content = Zlib::Deflate.deflate(store)
   => "x\x9CK\xCA\xC9OR04c(\xCFH,Q\xC8,V(-\xD0QH\xC9O\xB6\a\x00_\x1C\a\x9D"
   ```
6. Then, open the file with `File.open()` and write out the previously zlib-compressed content to the file with a `write()` call on the resulting file handle:
   ```text
   >> path = '.git/objects/' + sha1[0,2] + '/' + sha1[2,38]
   => ".git/objects/bd/9dbf5aae1a3862dd1526723246b20206e5fc37"
   >> require 'fileutils'
   => true
   >> FileUtils.mkdir_p(File.dirname(path))
   => ".git/objects/bd"
   >> File.open(path, 'w') { |f| f.write zlib_content }
   => 32
   ```
7. Let’s check the content of the object using `git cat-file`:
   ```bash
   git cat-file -p bd9dbf5aae1a3862dd1526723246b20206e5fc37
   ```
   Expected output (excerpt):
   ```text
   what is up, doc?
   ```
8. Run:
   ```text
   ---
   ```

**Verify:** run `git cat-file -p bd9dbf5aae1a3862dd1526723246b20206e5fc37` - expect something like:
```text
what is up, doc?
```
