# Appendix B: Embedding Git in your Applications

_Source: Pro Git, pages 472-483_

## Topics covered

- Command-line Git
- Libgit2
- JGit
- go-git
- Dulwich

**Key terms:** jgit, libgit2, go-git, bindings, repo, eclipse, odb, apis, api, object

## Key points

- If you need to integrate Git with your application, you have essentially two options: spawn a shell and call the git command-line program, or embed a Git library into your application.
- Let’s take a look at the above example written using the Ruby bindings for Libgit2, which are named Rugged, and can be found at https://github.com/libgit2/rugged. repo = Rugged::Repository.new('path/to/repository') commit = repo.head.target puts commit.message puts "#{commit.author[:name]} <#{commit.author[:email]}>" tree = commit.tree As you can see, the code is much less cluttered.
- The return value is the SHA-1 hash of a new commit object, which you can then use to get a Commit object.
- Objective-Git ( https://github.com/libgit2/objective-git) is the name of the Libgit2 bindings for that environment.
- If you want more information on Libgit2 itself, there’s API documentation at https://libgit2.github.com/libgit2, and a set of guides at https://libgit2.github.com/docs.
- JGit If you want to use Git from within a Java program, there is a fully featured Git library called JGit.
- As soon as you have a Repository instance, you can access information and perform mutations on it: // retrieves the branch pointed by HEAD ref, err := r.Head() // get the commit object, pointed by ref commit, err := r.CommitObject(ref.Hash()) // retrieves the commit history history, err := commit.History() // iterates over the commits and print each
- If you want more information on go-git, there’s API documentation at https://pkg.go.dev/github.com/go-git/go-git/v5, and a set of usage examples at https://github.com/go-git/go-git/tree/master/_examples.

## Commands / code

```
git_repository *repo;
int error = git_repository_open(&repo, "/path/to/repository");
git_object *head_commit;
error = git_revparse_single(&head_commit, repo, "HEAD^{commit}");
git_commit *commit = (git_commit*)head_commit;
printf("%s", git_commit_message(commit));
const git_signature *author = git_commit_author(commit);
printf("%s <%s>\n", author->name, author->email);
const git_oid *tree_id = git_commit_tree_id(commit);
git_commit_free(commit);
git_repository_free(repo);
sig = {
git_odb *odb;
int error = git_odb_new(&odb);
git_odb_backend *my_backend;
error = git_odb_backend_mine(&my_backend, /*…*/);
error = git_odb_add_backend(odb, my_backend, 1);
error = git_repository_open(&repo, "some-path");
error = git_repository_set_odb(repo, odb);
typedef struct {
git_odb_backend parent;
void *custom_context;
} my_backend_struct;
my_backend_struct *backend;
backend = calloc(1, sizeof (my_backend_struct));
backend->custom_context = …;
backend->parent.read = &my_backend__read;
backend->parent.read_prefix = &my_backend__read_prefix;
backend->parent.read_header = &my_backend__read_header;
*backend_out = (git_odb_backend *) backend;
return GIT_SUCCESS;
new Repository(@"C:\path\to\repo").Head.Tip.Message;
error:NULL];
NSString *msg = [[[repo headReferenceWithError:NULL] resolvedTarget] message];
<dependency>
<groupId>org.eclipse.jgit</groupId>
<artifactId>org.eclipse.jgit</artifactId>
<version>3.5.0.201409260305-r</version>
new File("/tmp/new_repo/.git"));
newlyCreatedRepo.create();
```

## Rules, tips and warnings

- The type returned is a git_object pointer, which represents something that exists in the Git object database for a repository. git_object is actually a “parent” type for several different kinds of objects; the memory layout for each of the “child” types is the same as for git_object, so you can safely cast to the right one.
- Let’s take a look at the above example written using the Ruby bindings for Libgit2, which are named Rugged, and can be found at https://github.com/libgit2/rugged. repo = Rugged::Repository.new('path/to/repository') commit = repo.head.target puts commit.message puts "#{commit.author[:name]} <#{commit.author[:email]}>" tree = commit.tree As you can see, the code is much less cluttered.
- This uses the tip of HEAD for the single parent.
- The return value is the SHA-1 hash of a new commit object, which you can then use to get a Commit object.
- One example is pluggability: Libgit2 allows you to provide custom “backends” for several types of operation, so you can store things in a different way than stock Git does.
- Note that errors are captured, but not handled.
- Well, that’s the constructor for your own ODB implementation, and you can do whatever you want in there, so long as you fill in the git_odb_backend structure properly.
- The subtlest constraint here is that my_backend_struct’s first member must be a git_odb_backend structure; this ensures that the memory layout is what the Libgit2 code expects it to be.
- If you want more information on Libgit2 itself, there’s API documentation at https://libgit2.github.com/libgit2, and a set of guides at https://libgit2.github.com/docs.
- JGit If you want to use Git from within a Java program, there is a fully featured Git library called JGit.
- You can build them into your project by running a command like this: javac -cp .:org.eclipse.jgit-3.5.0.201409260305-r.jar App.java java -cp .:org.eclipse.jgit-3.5.0.201409260305-r.jar App Plumbing JGit has two basic levels of API: plumbing and porcelain.
- Once you have a Repository instance, you can do all sorts of things with it.
