# More procedures: Interactive Staging

### Staging and Unstaging Files

**Goal:** The `*` next to each file means the file is selected to be staged.

**Steps:**

1. If you type `u` or `2` (for update) at the `What now>` prompt, you’re prompted for which files you want to stage:
   ```text
   What now> u
              staged     unstaged path
     1:    unchanged        +0/-1 TODO
   ```
2. Run:
   ```text
     2:    unchanged        +1/-1 index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   Update>>
   ```
3. To stage the `TODO` and `index.html` files, you can type the numbers:
   ```text
   Update>> 1,2
              staged     unstaged path
   * 1:    unchanged        +0/-1 TODO
   * 2:    unchanged        +1/-1 index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   Update>>
   ```
4. If you press Enter after typing nothing at the `Update>>` prompt, Git takes anything selected and stages it for you:
   ```text
   Update>>
   updated 2 paths
   *** Commands ***
     1: [s]tatus     2: [u]pdate      3: [r]evert     4: [a]dd untracked
     5: [p]atch      6: [d]iff        7: [q]uit       8: [h]elp
   What now> s
              staged     unstaged path
     1:        +0/-1      nothing TODO
     2:        +1/-1      nothing index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   ```
5. If you want to unstage the `TODO` file at this point, you use the `r` or `3` (for revert) option:
   ```text
   *** Commands ***
     1: [s]tatus     2: [u]pdate      3: [r]evert     4: [a]dd untracked
     5: [p]atch      6: [d]iff        7: [q]uit       8: [h]elp
   What now> r
              staged     unstaged path
     1:        +0/-1      nothing TODO
     2:        +1/-1      nothing index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   Revert>> 1
              staged     unstaged path
   * 1:        +0/-1      nothing TODO
     2:        +1/-1      nothing index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   Revert>> [enter]
   reverted one path
   ```
6. Looking at your Git status again, you can see that you’ve unstaged the `TODO` file:
   ```text
   *** Commands ***
     1: [s]tatus     2: [u]pdate      3: [r]evert     4: [a]dd untracked
     5: [p]atch      6: [d]iff        7: [q]uit       8: [h]elp
   What now> s
              staged     unstaged path
     1:    unchanged        +0/-1 TODO
     2:        +1/-1      nothing index.html
     3:    unchanged        +5/-1 lib/simplegit.rb
   ```
7. This is much like specifying `git diff --cached` on the command line:
   ```text
   *** Commands ***
     1: [s]tatus     2: [u]pdate      3: [r]evert     4: [a]dd untracked
     5: [p]atch      6: [d]iff        7: [q]uit       8: [h]elp
   What now> d
              staged     unstaged path
     1:        +1/-1      nothing index.html
   Review diff>> 1
   diff --git a/index.html b/index.html
   index 4d07108..4335f49 100644
   --- a/index.html
   +++ b/index.html
   @@ -16,7 +16,7 @@ Date Finder
    <p id="out">...</p>
   -<div id="footer">contact : support@github.com</div>
   +<div id="footer">contact : email.support@github.com</div>
    <script type="text/javascript">
   ```

**If it fails:** If you want to unstage the `TODO` file at this point, you use the `r` or `3` (for revert) option:
