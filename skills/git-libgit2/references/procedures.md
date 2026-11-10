# More procedures: Libgit2

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
       :update_ref => 'HEAD', ⑦
   )
   commit = repo.lookup(commit_id) ⑧
   ```
