---
name: git-jgit
description: "Use git from Java with JGit: add the dependency, open a repository, the plumbing API (Repository, ObjectId, RevWalk) and the porcelain Git class. Use when the user writes Java code that reads or changes a git repository."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "JGit"
  category: git-integrations
  source: "Pro Git, 2nd edition"
  pages: "477-480"
---

# JGit

JGit is a relatively full-featured implementation of Git written natively in Java, and is widely used in the Java community.

_Built from "Pro Git" (pages 477-480) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **jgit** (fully featured git, featured git library, git library called, library called jgit, object).
- If you want to use Git from within a Java program, there is a fully featured Git library called JGit.
- JGit automatically grabs the actual`master` ref, which lives at `refs/heads/master`, and returns an object that lets you fetch information about the reference.

## When NOT to use

- For libgit2, use the `git-libgit2` skill instead.
- For git as a client, use the `git-as-a-client` skill instead.
- For scripting github, use the `git-scripting-github` skill instead.

## Key concepts

- If you want to use Git from within a Java program, there is a fully featured Git library called JGit.
- The JGit project is under the Eclipse umbrella, and its home can be found at https://projects.eclipse.org/projects/technology.jgit.
- JGit has two basic levels of API: plumbing and porcelain.
- The terminology for these comes from Git itself, and JGit is divided into roughly the same kinds of areas: porcelain APIs are a friendly front-end for common user-level actions (the sorts of things a normal user would use the Git command-line tool for), while the plumbing APIs are for interacting with low-level repository objects directly.
- The starting point for most JGit sessions is the `Repository` class, and the first thing you’ll want to do is create an instance of it.
- JGit automatically grabs the actual`master` ref, which lives at `refs/heads/master`, and returns an object that lets you fetch information about the reference.
- The third line is similar, but shows how JGit handles the rev-parse syntax (for more on this, see Branch References); you can pass any object specifier that Git understands, and JGit will return either a valid ObjectId for that object, or `null`.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Getting Set Up

**Goal:** There are a number of ways to connect your project with JGit and start writing code against it.

**Steps:**

1. Probably the easiest is to use Maven – the integration is accomplished by adding the following snippet to the `<dependencies>` tag in your `pom.xml` file:
   ```text
   <dependency>
       <groupId>org.eclipse.jgit</groupId>
       <artifactId>org.eclipse.jgit</artifactId>
       <version>3.5.0.201409260305-r</version>
   </dependency>
   ```
2. The
   ```text
   version
   ```
3. You can build them into your project by running a command like this:
   ```text
   javac -cp .:org.eclipse.jgit-3.5.0.201409260305-r.jar App.java
   java -cp .:org.eclipse.jgit-3.5.0.201409260305-r.jar App
   ```

### Plumbing

**Goal:** The starting point for most JGit sessions is the `Repository` class, and the first thing you’ll want to do is create an instance of it.

**Steps:**

1. For a filesystem-based repository (yes, JGit allows for other storage models), this is accomplished using `FileRepositoryBuilder`:
   ```text
   // Create a new repository
   Repository newlyCreatedRepo = FileRepositoryBuilder.create(
       new File("/tmp/new_repo/.git"));
   newlyCreatedRepo.create();
   // Open an existing repository
   Repository existingRepo = new FileRepositoryBuilder()
       .setGitDir(new File("my_repo/.git"))
       .build();
   ```
2. Here’s a quick sampling:
   ```text
   // Get a reference
   Ref master = repo.getRef("master");
   // Get the object the reference points to
   ObjectId masterTip = master.getObjectId();
   // Rev-parse
   ObjectId obj = repo.resolve("HEAD^{tree}");
   // Load raw object contents
   ObjectLoader loader = repo.open(masterTip);
   loader.copyTo(System.out);
   // Create a branch
   RefUpdate createBranch1 = repo.updateRef("refs/heads/branch1");
   createBranch1.setNewObjectId(masterTip);
   ```
3. Run:
   ```text
   createBranch1.update();
   // Delete a branch
   RefUpdate deleteBranch1 = repo.updateRef("refs/heads/branch1");
   deleteBranch1.setForceUpdate(true);
   deleteBranch1.delete();
   // Config
   Config cfg = repo.getConfig();
   String name = cfg.getString("user", null, "name");
   ```

### Porcelain

**Goal:** Porcelain

**Steps:**

1. JGit provides a higher-level set of APIs to help out with this, and the entry point to these APIs is the `Git` class:
   ```text
   Repository repo;
   // construct repo...
   Git git = new Git(repo);
   ```
2. Let’s take a look at an example — doing something like `git ls-remote`:
   ```text
   CredentialsProvider cp = new UsernamePasswordCredentialsProvider("username",
   "p4ssw0rd");
   Collection<Ref> remoteRefs = git.lsRemote()
       .setCredentialsProvider(cp)
       .setRemote("origin")
       .setTags(true)
       .setHeads(false)
       .call();
   for (Ref ref : remoteRefs) {
       System.out.println(ref.getName() + " -> " + ref.getObjectId().name());
   }
   ```

**If it fails:** Many other commands are available through the Git class, including but not limited to `add`, `blame`, `commit`, `clean`, `push`, `rebase`, `revert`, and `reset`.

## Related skills

- `git-libgit2` - Libgit2
- `git-as-a-client` - Git as a Client
- `git-scripting-github` - Scripting GitHub
- `git-plumbing-and-porcelain` - Plumbing and Porcelain

## Source

"Pro Git", pages 477-480. Sections: JGit; JGit > Getting Set Up; JGit > Plumbing; JGit > Porcelain; JGit > Further Reading.
