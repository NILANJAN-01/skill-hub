# More procedures: Git Attributes

### Binary Files

**Goal:** One cool trick for which you can use Git attributes is telling Git which files are binary (in cases it otherwise may not be able to figure out) and giving Git special instructions about how to handle those files.

**Steps:**

1. To tell Git to treat all `pbxproj` files as binary data, add the following line to your `.gitattributes` file:
   ```text
   *.pbxproj binary
   ```
2. If you run `git diff` normally, you only see something like this:
   ```bash
   git diff
   ```
   Expected output (excerpt):
   ```text
   diff --git a/chapter1.docx b/chapter1.docx
   index 88839c4..4afcb7c 100644
   Binary files a/chapter1.docx and b/chapter1.docx differ
   ```
3. Put the following line in your `.gitattributes` file:
   ```text
   *.docx diff=word
   ```
4. Create a file that’s somewhere in your path called `docx2txt`, and add these contents:
   ```bash
   #!/bin/bash
   docx2txt.pl "$1" -
   ```
5. Finally, you can configure Git to use this script:
   ```bash
   git config diff.word.textconv docx2txt
   ```
6. Here’s what `git diff` shows:
   ```bash
   git diff
   ```
   Expected output (excerpt):
   ```text
   diff --git a/chapter1.docx b/chapter1.docx
   index 0b013ca..ba25db5 100644
   --- a/chapter1.docx
   +++ b/chapter1.docx
   ```
7. Put the following line in your `.gitattributes` file:
   ```text
   *.png diff=exif
   ```
8. Configure Git to use this tool:
   ```bash
   git config diff.exif.textconv exiftool
   ```
9. If you replace an image in your project and run `git diff`, you see something like this:
   ```text
   diff --git a/image.png b/image.png
   index 88839c4..4afcb7c 100644
   --- a/image.png
   +++ b/image.png
   @@ -1,12 +1,12 @@
    ExifTool Version Number         : 7.74
   -File Size                       : 70 kB
   -File Modification Date/Time     : 2009:04:21 07:02:45-07:00
   +File Size                       : 94 kB
   +File Modification Date/Time     : 2009:04:21 07:02:43-07:00
    File Type                       : PNG
    MIME Type                       : image/png
   -Image Width                     : 1058
   -Image Height                    : 889
   +Image Width                     : 1056
   +Image Height                    : 827
    Bit Depth                       : 8
    Color Type                      : RGB with Alpha
   ```

**Verify:** run `git diff` - expect something like:
```text
diff --git a/chapter1.docx b/chapter1.docx
index 0b013ca..ba25db5 100644
--- a/chapter1.docx
+++ b/chapter1.docx
@@ -2,6 +2,7 @@
 This chapter will be about getting started with Git. We will begin at the beginning
```

**If it fails:** Now, Git won’t try to convert or fix CRLF issues; nor will it try to compute or print a diff for changes in this file when you run `git show` or `git diff` on your project.

### Keyword Expansion

**Goal:** Git attributes offers you two ways to do this.

**Steps:**

1. Put the following line in your `.gitattributes` file:
   ```text
   *.txt ident
   ```
2. Add an `$Id$` reference to a test file:
   ```bash
   echo '$Id$' > test.txt
   ```
3. The next time you check out this file, Git injects the SHA-1 of the blob:
   ```bash
   rm test.txt
   git checkout -- test.txt
   cat test.txt
   ```
   Expected output (excerpt):
   ```text
   $Id: 42812b7653c7b88933f8a9d6cad0ca16714b9bb3 $
   ```
4. You can set it up by setting the filter attribute in your `.gitattributes` file to filter `\*.c` files with the “indent” filter:
   ```text
   *.c filter=indent
   ```
5. Then, tell Git what the “indent” filter does on smudge and clean:
   ```bash
   git config --global filter.indent.clean indent
   git config --global filter.indent.smudge cat
   ```
6. Here is a small Ruby script that does that:
   ```ruby
   #! /usr/bin/env ruby
   data = STDIN.read
   last_date = `git log --pretty=format:"%ad" -1`
   puts data.gsub('$Date$', '$Date: ' + last_date.to_s + '$')
   ```
7. You’ll use a Perl expression to clean that up on commit:
   ```bash
   git config filter.dater.smudge expand_date
   git config filter.dater.clean 'perl -pe "s/\\\$Date[^\\\$]*\\\$/\\\$Date\\\$/"'
   ```
8. Now that your filter is ready, you can test it by setting up a Git attribute for that file that engages the new filter and creating a file with your `$Date$` keyword:
   ```bash
   echo '# $Date$' > date_test.txt
   ```
9. If you commit those changes and check out the file again, you see the keyword properly substituted:
   ```bash
   git add date_test.txt .gitattributes
   git commit -m "Test date expansion in Git"
   rm date_test.txt
   git checkout date_test.txt
   cat date_test.txt
   ```
   Expected output (excerpt):
   ```text
   # $Date: Tue Apr 21 07:26:52 2009 -0700$
   ```

**If it fails:** This Perl snippet strips out anything it sees in a `$Date$` string, to get back to where you started.
