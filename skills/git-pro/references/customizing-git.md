# Customizing Git

_Source: Pro Git, pages 342-372_

## Topics covered

- Git Configuration
- Git Attributes
- Git Hooks
- An Example Git-Enforced Policy
- Summary

**Key terms:** hook, file, commit, extmerge, acl, hooks, script, docx, run, git

## Key points

- Customizing Git So far, we’ve covered the basics of how Git works and how to use it, and we’ve introduced a number of tools that Git provides to help you use it easily and efficiently.
- The next place Git looks is the ~/.gitconfig (or ~/.config/git/config) file, which is specific to each user.
- Finally, Git looks for configuration values in the configuration file in the Git directory ( .git/config) of whatever repository you’re currently using.
- Now, no matter what is set as your default shell editor, Git will fire up Emacs to edit messages. commit.template If you set this to the path of a file on your system, Git will use that file as the default initial message when you commit.
- To tell Git to use it as the default message that appears in your editor when you run git commit, set the commit.template configuration value: `git config --global commit.template ~/.gitmessage.txt`.
- You can put patterns in your project’s .gitignore file to have Git not see them as untracked files or try to stage them when you run git add on them, as discussed in Ignoring Files.
- If you create a ~/.gitignore_global file with these contents: *~ .*.swp .DS_Store …and you run git config --global core.excludesfile ~/.gitignore_global , Git will never again bother you about those files. help.autocorrect If you mistype a command, it shows you something like this: `git chekcout master`.
- If you set help.autocorrect to 1, Git will actually run this command for you: `git chekcout master`.
- This takes a number of custom settings: merge.tool to tell Git what strategy to use, mergetool.<tool>.cmd to specify how to run the command, mergetool.<tool>.trustExitCode to tell Git if the exit code of that program indicates a successful merge resolution or not, and diff.external to tell Git what command to run for diffs.
- Git will detect these issues when you run a git diff command and try to color them so you can possibly fix them before you commit.
- These path-specific settings are called Git attributes and are set either in a .gitattributes file in one of your directories (normally the root of your project) or in the .git/info/attributes file if you don’t want the attributes file committed with your project.
- Using attributes, you can do things like specify separate merge strategies for individual files or directories in your project, tell Git how to diff non-text files, or have Git filter content before you check it into or out of Git.
- Binary Files One cool trick for which you can use Git attributes is telling Git which files are binary (in cases it otherwise may not be able to figure out) and giving Git special instructions about how to handle those files.
- To tell Git to treat all pbxproj files as binary data, add the following line to your .gitattributes file: *.pbxproj binary Now, Git won’t try to convert or fix CRLF issues; nor will it try to compute or print a diff for changes in this file when you run git show or git diff on your project.
- If you run git diff normally, you only see something like this: `git diff`.
- The main problem with this in Git is that you can’t modify a file with information about the commit after you’ve committed, because Git checksums the file first.
- You can set it up by setting the filter attribute in your .gitattributes file to filter \*.c files with the “indent” filter: *.c filter=indent Then, tell Git what the “indent” filter does on smudge and clean: `git config --global filter.indent.clean indent`.
- You can add the following line to your Git attributes file: test/ export-ignore Now, when you run git archive to create a tarball of your project, that directory won’t be included in the archive. export-subst When exporting files for deployment you can apply git log’s formatting and keyword-expansion processing to selected portions of files marked with the export-subst attribute.
- Merge Strategies You can also use Git attributes to tell Git to use different merge strategies for specific files in your project.
- The post-rewrite hook is run by commands that replace commits, such as git commit --amend and git rebase (though not by git filter-branch).
- You can pretty easily see what files have been modified in a single commit with the --name-only option to the git log command (mentioned briefly in Git Basics): `git log -1 --name-only --pretty=format:'' 9f585d`.
- Testing It Out If you run chmod u+x .git/hooks/update , which is the file into which you should have put all this code, and then try to push a commit with a non-compliant message, you get something like this: `git push -f origin master`.
- Lastly, you have this: To git@gitserver:project.git ! [remote rejected] master -> master (hook declined) error: failed to push some refs to 'git@gitserver:project.git' You’ll see a remote rejected message for each reference that your hook declined, and it tells you that it was declined specifically because of a hook failure.
- However, if your message contains the proper pattern, Git allows you to commit: `git commit -am 'Test [ref: 132]'`.

## Commands / code

```
$ git config --global user.name "John Doe"
$ git config --global user.email johndoe@example.com
$ man git-config
$ git config --global core.editor emacs
$ git config --global commit.template ~/.gitmessage.txt
$ git commit
$ git config --global core.pager ''
$ git config --global user.signingkey <gpg-key-id>
$ git tag -s <tag-name>
$ git chekcout master
$ git config --global color.ui false
$ git config --global color.diff.meta "blue black bold"
$ cat /usr/local/bin/extMerge
$ cat /usr/local/bin/extDiff
$ sudo chmod +x /usr/local/bin/extMerge
$ sudo chmod +x /usr/local/bin/extDiff
$ git config --global merge.tool extMerge
$ git config --global mergetool.extMerge.cmd \
$ git config --global mergetool.extMerge.trustExitCode false
$ git config --global diff.external extDiff
$ git diff 32d1776b1^ 32d1776b1
$ git mergetool --tool-help
$ git config --global merge.tool kdiff3
$ git config --global core.autocrlf true
$ git config --global core.autocrlf input
$ git config --global core.autocrlf false
$ git config --global core.whitespace \
$ git apply --whitespace=warn <patch>
$ git apply --whitespace=fix <patch>
$ git config --system receive.fsckObjects true
$ git config --system receive.denyNonFastForwards true
$ git config --system receive.denyDeletes true
$ git diff
$ git config diff.word.textconv docx2txt
$ git config diff.exif.textconv exiftool
$ echo '$Id$' > test.txt
$ rm test.txt
$ git checkout -- test.txt
$ cat test.txt
$ git config --global filter.indent.clean indent
```

## Rules, tips and warnings

- You can make Git read and write to this file by passing the --global option.
- Each of these “levels” (system, global, local) overwrites values in the previous level, so values in .git/config trump those in [path]/etc/gitconfig, for instance.  Git’s configuration files are plain-text, so you can also set these values by manually editing the file and inserting the correct syntax.
- If you want to see a list of all the options your version of Git recognizes, you can run: `man git-config`.
- To change that default to something else, you can use the core.editor setting: `git config --global core.editor emacs`.
- The value in creating a custom commit template is that you can use it to remind yourself (or others) of the proper format and style when creating a commit message.
- You can set it to more or to your favorite pager (by default, it’s less), or you can turn it off by setting it to a blank string: `git config --global core.pager ''`.
- Now, you can sign tags without having to specify your key every time with the git tag command: `git tag -s <tag-name>`.
- You can put patterns in your project’s .gitignore file to have Git not see them as untracked files or try to stage them when you run git add on them, as discussed in Ignoring Files.
- If you create a ~/.gitignore_global file with these contents: *~ .*.swp .DS_Store …and you run git config --global core.excludesfile ~/.gitignore_global , Git will never again bother you about those files. help.autocorrect If you mistype a command, it shows you something like this: `git chekcout master`.
- Note that “0.1 seconds” business. help.autocorrect is actually an integer which represents tenths of a second.
- You can also set it to always to ignore the difference between terminals and pipes.
- You’ll rarely want this; in most scenarios, if you want color codes in your redirected output, you can instead pass a --color flag to the Git command to force it to use color codes.
