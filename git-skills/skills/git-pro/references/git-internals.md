# Git Internals

_Source: Pro Git, pages 420-458_

## Topics covered

- Plumbing and Porcelain
- Git Objects
- Git References
- Packfiles
- The Refspec
- Transfer Protocols
- Maintenance and Data Recovery
- Environment Variables
- Summary

**Key terms:** objects, packfile, file, refs, trace, pack, object, test, commit, cat-file

## Key points

- When you run git init in a new or existing directory, Git creates the .git directory, which is where almost everything that Git stores and manipulates is located.
- Git Objects Git is a content-addressable filesystem.
- As a demonstration, let’s look at the plumbing command git hash-object, which takes some data, stores it in your .git/objects directory (the object database), and gives you back the unique key that now refers to that data object.
- First, you initialize a new Git repository and verify that there is (predictably) nothing in the objects directory: `git init test`.
- Now, let’s use git hash-object to create a new data object and manually store it in your new Git database: `echo 'test content' | git hash-object -w --stdin`.
- Now you can see how Git has stored your data: `find .git/objects -type f`.
- You can have Git tell you the object type of any object in Git, given its SHA-1 key, with git cat-file -t: `git cat-file -t 1f7a7a472abf3dd9643fd615f6da379c4acb3e3a`.
- Now you can look at your new commit object with git cat-file: `git cat-file -p fdf4fc3`.
- Oddly enough, you have a real Git history now that you can view with the git log command, if you run it on the last commit SHA-1: `git log --stat 1a410e`.
- This is essentially what Git does when you run the git add and git commit commands — it stores blobs for the files that have changed, updates the index, writes out trees, and writes commit objects that reference the top-level trees and the commits that came immediately before them.
- These three main Git objects — the blob, the tree, and the commit — are initially stored as separate files in your .git/objects directory.
- All the reachable objects in your Git directory Object Storage We mentioned earlier that there is a header stored with every object you commit to your Git object database.
- Then, open the file with File.open() and write out the previously zlib-compressed content to the file with a write() call on the resulting file handle: >> path = '.git/objects/' + sha1[0,2] + '/' + sha1[2,38] => ".git/objects/bd/9dbf5aae1a3862dd1526723246b20206e5fc37" >> require 'fileutils' => true >> FileUtils.mkdir_p(File.dirname(path)) => ".git/objects/bd"
- Let’s check the content of the object using git cat-file: --- `git cat-file -p bd9dbf5aae1a3862dd1526723246b20206e5fc37`.
- You aren’t encouraged to directly edit the reference files; instead, Git provides the safer command git update-ref to do this if you want to update a reference: `git update-ref refs/heads/master 1a410efbd13591db07496601ebc7a059dd55cfe9`.
- Git directory objects with branch head references included When you run commands like git branch <branch>, Git basically runs that update-ref command to add the SHA-1 of the last commit of the branch you’re on into whatever new reference you want to create.
- The HEAD The question now is, when you run git branch <branch>, how does Git know the SHA-1 of the last commit?
- If you run git checkout test, Git updates the file to look like this: `cat .git/HEAD`.
- For instance, you can add a remote called origin and push your master branch to it: `git remote add origin git@github.com:schacon/simplegit-progit.git`.
- You can then use git cat-file to see how large that object is: `git cat-file -s 033b4468fa6b2a9547a70d88d1bbe8bf3f9ed0d5`.
- To see what happens, you can manually ask Git to pack up the objects by calling the git gc command: `git gc`.
- The git verify-pack plumbing command allows you to see what was packed up: `git verify-pack -v .git/objects/pack/pack978e03944f5c581011e6998cd0e9e30000905586.idx`.
- However, if there are too many loose objects (objects not in a packfile) or too many packfiles, Git launches a full-fledged git gc command.
- Git will move them for the sake of efficiency into a file named .git/packed-refs that looks like this: `cat .git/packed-refs`.
- You can see where you’ve been at any time by running git reflog: `git reflog`.

## Commands / code

```
$ ls -F1
$ git init test
$ cd test
$ find .git/objects
$ find .git/objects -type f
$ echo 'test content' | git hash-object -w --stdin
$ git cat-file -p d670460b4b4aece5915caf5c68d12f560a9fe3e4
$ echo 'version 1' > test.txt
$ git hash-object -w test.txt
$ echo 'version 2' > test.txt
$ git cat-file -p 83baae61804e65cc73a7201a7252750c76066a30 > test.txt
$ cat test.txt
$ git cat-file -p 1f7a7a472abf3dd9643fd615f6da379c4acb3e3a > test.txt
$ git cat-file -t 1f7a7a472abf3dd9643fd615f6da379c4acb3e3a
$ git cat-file -p master^{tree}
$ git cat-file -p 99f1a6d12cb4b6f19c8655fca46c3ecf317074e0
$ git update-index --add --cacheinfo 100644 \
$ git write-tree
$ git cat-file -p d8329fc1cc938780ffdd9f94e0d364e0ea74f579
$ git cat-file -t d8329fc1cc938780ffdd9f94e0d364e0ea74f579
$ echo 'new file' > new.txt
$ git update-index --cacheinfo 100644 \
$ git update-index --add new.txt
$ git cat-file -p 0155eb4229851634a0f03eb265b69f5a2d56f341
$ git read-tree --prefix=bak d8329fc1cc938780ffdd9f94e0d364e0ea74f579
$ git cat-file -p 3c4e9cd789d88d8d89c1073707c3585e41b0e614
$ echo 'First commit' | git commit-tree d8329f
$ git cat-file -p fdf4fc3
$ echo 'Second commit' | git commit-tree 0155eb -p fdf4fc3
$ echo 'Third commit'  | git commit-tree 3c4e9c -p cac0cab
$ git log --stat 1a410e
$ irb
$ echo -n "what is up, doc?" | git hash-object --stdin
>> File.open(path, 'w') { |f| f.write zlib_content }
$ git cat-file -p bd9dbf5aae1a3862dd1526723246b20206e5fc37
$ find .git/refs
$ find .git/refs -type f
$ echo 1a410efbd13591db07496601ebc7a059dd55cfe9 > .git/refs/heads/master
$ git log --pretty=oneline master
$ git update-ref refs/heads/master 1a410efbd13591db07496601ebc7a059dd55cfe9
```

## Rules, tips and warnings

- We found that understanding this information was fundamentally important to appreciating how useful and powerful Git is, but others have argued to us that it can be confusing and unnecessarily complex for beginners.
- If you want to back up or clone your repository, copying this single directory elsewhere gives you nearly everything you need.
- This entire chapter basically deals with what you can see in this directory.
- This leaves four important entries: the HEAD and (yet to be created) index files, and the objects and refs directories.
- What this means is that you can insert any kind of content into a Git repository, for which Git will hand you back a unique key you can use later to retrieve that content.
- Now you can see how Git has stored your data: `find .git/objects -type f`.
- If you again examine your objects directory, you can see that it now contains a file for that new content.
- Once you have content in your object database, you can examine that content with the git cat-file command.
- Now, you can add content to Git and pull it back out again.
- You can also do this with content in files.
- For example, you can do some simple version control on a file.
- At this point, you can delete your local copy of that test.txt file, then use Git to retrieve, from the object database, either the first version you saved: `git cat-file -p 83baae61804e65cc73a7201a7252750c76066a30 > test.txt`.
