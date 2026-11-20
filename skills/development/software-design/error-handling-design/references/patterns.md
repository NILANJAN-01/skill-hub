# Error-handling patterns by language

Original examples of the five techniques. Adapt the shape, not the names.

## 1. Define the error out of existence

### Idempotent removal (Python)

```python
def remove_file(path: Path) -> None:
    """Make sure path no longer exists. A missing file is already the goal state."""
    path.unlink(missing_ok=True)
```

### Clamped range instead of IndexOutOfBounds (Java)

```java
/** Returns the characters of s from index from (inclusive) to to (exclusive), clamped to
 *  the string; out-of-range or inverted bounds give the overlapping part, possibly "". */
static String slice(String s, int from, int to) {
    int start = Math.max(0, Math.min(from, s.length()));
    int end = Math.max(start, Math.min(to, s.length()));
    return s.substring(start, end);
}
```

### Empty object instead of null plus checks (TypeScript)

```ts
// Before: selection: Range | null, and `if (selection)` in 20 places.
// After: a selection always exists; "nothing selected" is an empty range at the cursor.
interface Range { start: number; end: number }          // start === end means empty
function deleteRange(text: string, r: Range): string {   // works for empty ranges too
  return text.slice(0, r.start) + text.slice(r.end);
}
```

### Lookup that returns "nothing" naturally (Go)

```go
// TagsFor returns the tags of the item, or an empty slice if it has none or does not exist.
// Callers that must distinguish a missing item use Exists.
func (s *Store) TagsFor(id string) []string { return s.tags[id] } // nil slice ranges fine
```

## 2. Mask the error low

### Retry inside the shared client (Kotlin)

```kotlin
/** Sends the request, retrying connection resets and 503s with jittered backoff for up to
 *  [deadline]. Throws ServiceUnavailable only if the service stays down for the whole deadline. */
fun send(req: Request): Response {
    var attempt = 0
    while (true) {
        try { return transport.send(req) }
        catch (e: TransientException) {
            if (clock.now() + backoff(attempt) > deadline) throw ServiceUnavailable(req.target, e)
            sleep(backoff(attempt++))
        }
    }
}
```

The application code that calls `send` contains no retry loops.

## 3. Aggregate many errors into one handler

### One handler at the request boundary (Python web service)

```python
class RequestError(Exception):
    """Aborts the current request; the message is safe to show to the client."""
    status = 400

class NotFound(RequestError):
    status = 404

def param_int(params, name):
    """Return parameter name as an int; raises RequestError with a readable message."""
    if name not in params:
        raise RequestError(f"missing parameter '{name}'")
    try:
        return int(params[name])
    except ValueError:
        raise RequestError(f"'{name}' must be a whole number, got {params[name]!r}") from None

def dispatch(request):
    try:
        return ROUTES[request.path](request)
    except RequestError as e:              # every request-level error, from any handler
        return Response(e.status, {"error": str(e)})
```

Handlers call `param_int(...)` freely and contain no `try` blocks.

### Same idea in C# (ASP.NET style middleware)

```csharp
// One place turns domain errors into HTTP responses; controllers just throw.
app.Use(async (ctx, next) => {
    try { await next(); }
    catch (RequestException e) { ctx.Response.StatusCode = e.Status; await ctx.Response.WriteAsJsonAsync(new { error = e.Message }); }
});
```

## 4. Crash on the unrecoverable

### Check once, abort with a message (Go)

```go
// mustLoadSchema is called once at startup; without the schema nothing can work,
// so a clear crash is better than error checks in every caller.
func mustLoadSchema(path string) *Schema {
    s, err := loadSchema(path)
    if err != nil {
        log.Fatalf("cannot start: schema %s: %v", path, err)
    }
    return s
}
```

### Internal invariant violated (Java)

```java
if (balance.signum() < 0) {
    throw new IllegalStateException("ledger corrupted: negative balance for " + accountId); // a bug, not a user error
}
```

## 5. Report it, and document it

When callers can and must act, report precisely and document the contract:

```ts
/**
 * Charges the card for the order total.
 * @throws CardDeclined when the issuer refuses the charge; show the reason to the customer and ask
 *         for another card. Nothing is charged.
 * @throws PaymentTimeout when the outcome is unknown; do NOT retry blindly: call status(orderId).
 */
async function charge(orderId: string, card: CardToken): Promise<Receipt> { ... }
```

## Anti-patterns

```python
try:
    do_work()
except Exception:
    pass                      # silent: hides bugs and outages
```

```java
try { a(); } catch (IOException e) { log.error("x", e); throw e; }   // logs at every level: noise, duplicates
```

```go
if err != nil {
    return err                // loses context; prefer fmt.Errorf("loading %s: %w", path, err)
}
```
