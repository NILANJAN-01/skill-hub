# GitHub

_Source: Pro Git, pages 172-223_

## Topics covered

- Account Setup and Configuration
- Contributing to a Project
- Maintaining a Project
- Managing an organization
- Scripting GitHub
- Summary

**Key terms:** request, pull, comment, notifications, github, button, blink, tonychacon, markdown, fork

## Key points

- Now if we go back to our fork on GitHub, we can see that GitHub noticed that we pushed a new topic branch up and presents us with a big green button to check out our changes and open a Pull Request to the original project.
- You can alternatively go to the “Branches” page at https://github.com/<user>/<project>/branches to locate your branch and open a new Pull Request from there.
- Comment on a specific line of code in a Pull Request Once the maintainer makes this comment, the person who opened the Pull Request (and indeed, anyone else watching the repository) will get a notification.
- If you merge this branch into the master branch and push it to GitHub, the Pull Request will automatically be closed.
- If you’re working on a feature with someone and you both have write access to the project, you can push a topic branch to the repository and open a Pull Request on it to the master branch of that same project to initiate the code review and discussion process.
- Pull Request does not merge cleanly If you see something like Pull Request does not merge cleanly, you’ll want to fix your branch so that it turns green and the maintainer doesn’t have to do extra work.
- If you want to merge in the target branch to make your Pull Request mergeable, you would add the original repository as a new remote, fetch from it, merge the main branch of that repository into your topic branch, fix any issues and finally push it back up to the same branch you opened the Pull Request on.
- Instead, push the rebased branch to a new branch on GitHub and open a brand new Pull Request referencing the old one, then close the original.
- Say we rebased the branch in the previous example, created a new pull request for it, and now we want to reference the old pull request from the new one.
- Now if Tony goes back and closes out the original Pull Request, we can see that by mentioning it in the new one, GitHub has automatically created a trackback event in the Pull Request timeline.
- The link will look something like Link back to the new Pull Request in the closed Pull Request timeline.
- The repository collaborators box Managing Pull Requests Now that you have a project with some code in it and maybe even a few collaborators who also have push access, let’s go over what to do when you get a Pull Request yourself.
- You should get an email notifying you about the new Pull Request and it should look something like Email notification of a new Pull Request.
- It gives you a link to the Pull Request on GitHub.
- You could technically merge in the Pull Request work with something like this: `curl https://github.com/tonychacon/fade/pull/1.patch | git am`.
- They will each have a link to the Pull Request where the activity is happening and you can also directly respond to the email to comment on the Pull Request thread.
- If the repository is on GitHub and you have any Pull Requests that have been opened, you’ll get these references that are prefixed with refs/pull/.
- There are two references per Pull Request - the one that ends in /head points to exactly the same commit as the last commit in the Pull Request branch.
- So if someone opens a Pull Request in our repository and their branch is named bug-fix and it points to commit a5a775, then in our repository we will not have a bug-fix branch (since that’s in their fork), but we will have pull/<pr#>/head that points to a5a775.
- Pull Requests on Pull Requests Not only can you open Pull Requests that target the main or master branch, you can actually open a Pull Request targeting any branch in the network.
- When you go to open a Pull Request, there is a box at the top of the page that specifies which branch you’re requesting to pull to and which you’re requesting to pull from.
- Manually change the Pull Request target fork and branch Here you can fairly easily specify to merge your new branch into another Pull Request or another fork of the project.
- Very often in Pull Requests on GitHub people will pull in other people on their teams or in their company to review an Issue or Pull Request.
- If you have a file named CONTRIBUTING with any file extension, GitHub will show Opening a Pull Request when a CONTRIBUTING file exists when anyone starts opening a Pull Request.
- Opening a Pull Request when a CONTRIBUTING file exists The idea here is that you can specify specific things you want or don’t want in a Pull Request sent to your project.

## Commands / code

```
$ git clone https://github.com/tonychacon/blink
$ cd blink
$ git checkout -b slow-blink
$ sed -i '' 's/1000/3000/' blink.ino (macOS)
$ git diff --word-diff
@@ -18,7 +18,7 @@ void setup() {
void loop() {
$ git commit -a -m 'Change delay to 3 seconds'
$ git push origin slow-blink
$ git remote add upstream https://github.com/schacon/blink
$ git fetch upstream
$ git merge upstream/master
$ vim blink.ino
$ git add blink.ino
$ git commit
System.out.println("i is : " + i);
> Whether 'tis Nobler in the mind to suffer
> The Slings and Arrows of outrageous Fortune,
$ git checkout master
$ git pull https://github.com/progit/progit2.git
$ git push origin master
$ git remote add progit https://github.com/progit/progit2.git
$ git fetch progit
$ git branch --set-upstream-to=progit/master master
$ git config --local remote.pushDefault origin
$ git pull
$ git push
$ curl https://github.com/tonychacon/fade/pull/1.patch | git am
$ git ls-remote https://github.com/schacon/blink
$ git fetch origin refs/pull/958/head
$ git fetch
$ git checkout pr/2
<user>/<project>/<type>/<id> format. If this was an issue, for example, the <type> field would have
$ curl https://api.github.com/users/schacon
$ curl https://api.github.com/gitignore/templates/Java
$ curl -H "Content-Type: application/json" \
"user": {
status = {
:headers => {
'Authorization' => "token #{ENV['TOKEN']}" }
```

## Rules, tips and warnings

- The “SSH keys” link From there, click the “Add an SSH key” button, give your key a name, paste the contents of your ~/.ssh/id_rsa.pub (or whatever you named it) public-key file into the text area, and click “Add key”.  Be sure to name your SSH key something you can remember.
- "My Laptop" or "Work Account") so that if you need to revoke a key later, you can easily tell which one you’re looking for.
- Your Avatar Next, if you wish, you can replace the avatar that is generated for you with an image of your choosing.
- The final address is unverified, meaning that you can’t make it your primary address.
- Two Factor Authentication Finally, for extra security, you should definitely set up Two-factor Authentication or “2FA”.
- You can find the Two-factor Authentication setup under the Security tab of your Account settings.
- Figure 87. 2FA in the Security Tab If you click on the “Set up two-factor authentication” button, it will take you to a configuration page where you can choose to use a phone app to generate your secondary code (a “time based one-time password”), or you can have GitHub send you a code via SMS each time you need to log in.
- Forking Projects If you want to contribute to an existing project to which you don’t have push access, you can “fork” the project.
- When you “fork” a project, GitHub will make a copy of the project that is entirely yours; it lives in your namespace, and you can push to it.  Historically, the term “fork” has been somewhat negative in context, meaning that someone took an open source project in a different direction, sometimes creating a competing project and splitting the contributors.
- Let’s walk through an example of proposing a change to an open source project hosted on GitHub using this flow.  You can use the official GitHub CLI tool instead of the GitHub web interface for most things.
- You can alternatively go to the “Branches” page at https://github.com/<user>/<project>/branches to locate your branch and open a new Pull Request from there.
- It is almost always worthwhile to put some effort into this, since a good description helps the owner of the original project determine what you were trying to do, whether your proposed changes are correct, and whether accepting the changes would improve the original project.
