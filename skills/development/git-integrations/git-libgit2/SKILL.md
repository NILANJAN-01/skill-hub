---
name: git-libgit2
description: "Use git from C, Ruby, .NET or Python through libgit2 bindings. Use when you need to embed git operations in an application."
license: CC BY-NC-SA 3.0. Derived from "Pro Git" by Scott Chacon and Ben Straub. See THIRD_PARTY_NOTICES.md
metadata:
  title: "Libgit2"
  category: git-integrations
  source: "Pro Git, 2nd edition"
  pages: "472-477"
---

# Libgit2

Objective-Git (https://github.com/libgit2/objective-git) is the name of the

_Built from "Pro Git" (pages 472-477) by extraction: statements below are quoted from the source. Full cleaned source: [references/source-text.md](references/source-text.md) - read it when a step needs more context._

## When to use

- The user asks about **libgit2** (object database, git repository, git object, structure, type).
- The user sees an error like `error = git_revparse_single(&head_commit, repo, "HEAD^{commit}");`.
- The user sees an error like `error = git_odb_backend_mine(&my_backend, /*…*/); ②`.
- The user sees an error like `error:NULL];`.
- One example is pluggability: Libgit2 allows you to provide custom “backends” for several types of operation, so you can store things in a different way than stock Git does.

## When NOT to use

- For scripting github, use the `git-scripting-github` skill instead.
- For jgit, use the `git-jgit` skill instead.
- For getting a git repository, use the `git-getting-a-git-repository` skill instead.

## Key concepts

- •If you declare a pointer and pass a reference to it into a Libgit2 call, that call will probably return an integer error code.
- •If Libgit2 returns a `const` pointer from a call, you don’t have to free it, but it will become invalid when the object it belongs to is freed.
- The code below is borrowed from the set of backend examples provided by the Libgit2 team (which can be found at https://github.com/libgit2/libgit2-backends).
- Libgit2 has bindings for many languages.
- The official collection of bindings can be found by browsing the repositories at https://github.com/libgit2.
- The bindings for Libgit2 in Python are called Pygit2, and can be found at https://www.pygit2.org.
- If you want more information on Libgit2 itself, there’s API documentation at https://libgit2.github.com/libgit2, and a set of guides at https://libgit2.github.com/docs.

## Safety rules for the agent

- Inspect the current state before changing anything (`git status`, current branch, uncommitted work, whether commits were already pushed) and tell the user what you are about to do.

## Procedures

### Libgit2

**Goal:** Libgit2 is a dependency-free implementation of

**Steps:**

1. Here’s a whirlwind tour:
   ```text
   // Open a repository
   git_repository *repo;
   int error = git_repository_open(&repo, "/path/to/repository");
   // Dereference HEAD to a commit
   git_object *head_commit;
   error = git_revparse_single(&head_commit, repo, "HEAD^{commit}");
   git_commit *commit = (git_commit*)head_commit;
   ```
2. Run:
   ```text
   // Print some of the commit's properties
   printf("%s", git_commit_message(commit));
   const git_signature *author = git_commit_author(commit);
   printf("%s <%s>\n", author->name, author->email);
   const git_oid *tree_id = git_commit_tree_id(commit);
   // Cleanup
   git_commit_free(commit);
   git_repository_free(repo);
   ```
3. Let’s take a look at the above example written using the Ruby bindings for Libgit2, which are named Rugged, and can be found at https://github.com/libgit2/rugged.
   ```ruby
   repo = Rugged::Repository.new('path/to/repository')
   commit = repo.head.target
   puts commit.message
   puts "#{commit.author[:name]} <#{commit.author[:email]}>"
   tree = commit.tree
   ```
4. crafting a commit from scratch
   ```text
   blob_id = repo.write("Blob contents", :blob) ①
   index = repo.index
   index.read_tree(repo.head.target.tree)
   index.add(:path => 'newfile.txt', :oid => blob_id) ②
   sig = {
       :email => "bob@example.com",
       :name => "Bob User",
       :time => Time.now,
   }
   commit_id = Rugged::Commit.create(repo,
       :tree => index.write_tree(repo), ③
       :author => sig,
       :committer => sig, ④
       :message => "Add newfile.txt", ⑤
       :parents => repo.empty? ? [] : [ repo.head.target ].compact, ⑥
   # ... (full listing in references)
   ```

### Advanced Functionality

**Goal:** One example is pluggability: Libgit2 allows you to provide custom “backends” for several types of operation, so you can store things in a different way than stock Git does.

**Steps:**

1. Here’s how a custom backend for the object database is set up:
   ```text
   git_odb *odb;
   int error = git_odb_new(&odb); ①
   git_odb_backend *my_backend;
   error = git_odb_backend_mine(&my_backend, /*…*/); ②
   error = git_odb_add_backend(odb, my_backend, 1); ③
   git_repository *repo;
   error = git_repository_open(&repo, "some-path");
   error = git_repository_set_odb(repo, odb); ④
   ```
2. Here’s what it could look like:
   ```text
   typedef struct {
       git_odb_backend parent;
       // Some other stuff
       void *custom_context;
   } my_backend_struct;
   int git_odb_backend_mine(git_odb_backend **backend_out, /*…*/)
   {
       my_backend_struct *backend;
       backend = calloc(1, sizeof (my_backend_struct));
       backend->custom_context = …;
       backend->parent.read = &my_backend__read;
       backend->parent.read_prefix = &my_backend__read_prefix;
       backend->parent.read_header = &my_backend__read_header;
   ```
3. Run:
   ```text
       // …
       *backend_out = (git_odb_backend *) backend;
       return GIT_SUCCESS;
   }
   ```

### Other Bindings

**Goal:** Objective-Git (https://github.com/libgit2/objective-git) is the name of the

**Steps:**

1. Here’s what our example program looks like:
   ```text
   new Repository(@"C:\path\to\repo").Head.Tip.Message;
   ```
2. The example program looks like this:
   ```text
   GTRepository *repo =
       [[GTRepository alloc] initWithURL:[NSURL fileURLWithPath: @"/path/to/repo"]
   error:NULL];
   NSString *msg = [[[repo headReferenceWithError:NULL] resolvedTarget] message];
   ```
3. Our example program:
   ```text
   pygit2.Repository("/path/to/repo") # open repository
       .head                          # get the current branch
       .peel(pygit2.Commit)           # walk down to the commit
       .message                       # read the message
   ```

More procedures in [references/procedures.md](references/procedures.md):

- Libgit2

## Decision guide

- In this case, `git_object_type(commit)` would return `GIT_OBJ_COMMIT`, so it’s safe to cast to a `git_commit` pointer.
- We hope your code is better than ours.

## Troubleshooting

| Symptom / message | What the source says next |
|---|---|
| `error = git_revparse_single(&head_commit, repo, "HEAD^{commit}");` | The first couple of lines open a Git repository. |
| `error = git_odb_backend_mine(&my_backend, /*…*/); ②` | Note that errors are captured, but not handled. |
| `error:NULL];` | Objective-git is fully interoperable with Swift, so don’t fear if you’ve left Objective-C behind. |


## Related skills

- `git-scripting-github` - Scripting GitHub
- `git-jgit` - JGit
- `git-getting-a-git-repository` - Getting a Git Repository
- `git-objects` - Git Objects

## Source

"Pro Git", pages 472-477. Sections: Libgit2; Libgit2 > Advanced Functionality; Libgit2 > Other Bindings; Libgit2 > Further Reading.
