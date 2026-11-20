# Deep modules: before and after

Original examples. Each shows one red flag and a fix. The point is the shape, not the domain.

## 1. Temporal decomposition and information leakage (Python)

Before: three classes split by phase. Both the loader and the saver know the CSV layout (column order, the date format, the header row).

```python
class InvoiceLoader:
    def load(self, path):
        rows = list(csv.reader(open(path)))[1:]          # knows: header row
        return [Invoice(r[0], datetime.strptime(r[1], "%d/%m/%Y"), Decimal(r[2])) for r in rows]

class InvoiceAdjuster:
    def apply_discount(self, invoices, pct): ...

class InvoiceSaver:
    def save(self, path, invoices):
        w = csv.writer(open(path, "w"))
        w.writerow(["id", "date", "amount"])            # knows: header and column order
        for i in invoices:
            w.writerow([i.id, i.date.strftime("%d/%m/%Y"), str(i.amount)])  # knows: date format
```

After: one module owns the file format, which is the knowledge, and serves both phases.

```python
class InvoiceFile:
    """Reads and writes invoices in the accounting team's CSV export format.

    Callers deal only in Invoice objects; column order, the header row and
    the day-first date format are private to this class.
    """
    def __init__(self, path): ...
    def read(self) -> list[Invoice]: ...
    def write(self, invoices: list[Invoice]) -> None: ...
```

A change to the date format now touches one class.

## 2. Pass-through methods (TypeScript)

Before: `OrderService` copies half of `OrderRepository`'s interface and adds nothing.

```ts
class OrderService {
  constructor(private repo: OrderRepository) {}
  find(id: string) { return this.repo.find(id); }
  save(order: Order) { return this.repo.save(order); }
  delete(id: string) { return this.repo.delete(id); }
  place(cart: Cart): Order { /* real work: pricing, stock, payment */ }
}
```

After: keep only the method that does work. Callers that need storage use the repository directly, or the service takes over the whole responsibility (pricing *and* persistence rules) so its methods are no longer copies.

```ts
class OrderService {
  constructor(private repo: OrderRepository, private payments: Payments) {}
  /** Prices the cart, reserves stock and charges the customer; returns the stored order. */
  place(cart: Cart): Order { /* ... */ }
}
```

## 3. Pass-through variable (Java)

Before: `tlsConfig` is threaded through three layers that never use it, only to reach the socket factory.

```java
void main(String[] args) { TlsConfig tls = parse(args); server.start(port, tls); }
void start(int port, TlsConfig tls) { acceptor.listen(port, tls); }
void listen(int port, TlsConfig tls) { connections.open(port, tls); }
void open(int port, TlsConfig tls) { socketFactory.create(port, tls); }   // the only real user
```

After: process-wide settings live in one context object created at startup. Long-lived objects keep a reference, so only constructors see it.

```java
/** Settings and shared services for one running server instance. Immutable after startup. */
final class ServerContext { final TlsConfig tls; final Clock clock; final Metrics metrics; ... }

class Connections {
    private final ServerContext ctx;
    Connections(ServerContext ctx) { this.ctx = ctx; }
    Connection open(int port) { return socketFactory.create(port, ctx.tls); }
}
```

## 4. Overexposure and pulling complexity down (Python)

Before: every caller must pick retry and timeout numbers it cannot know.

```python
def fetch(url, timeout_s, retries, backoff_s, retry_statuses, verify_tls): ...
fetch(url, 5, 3, 0.2, {502, 503}, True)          # repeated at 30 call sites
```

After: the module chooses good behaviour. The rare override is separate, so the common call has no knobs.

```python
class Http:
    """HTTP GET with sensible retry and timeout behaviour built in."""
    def fetch(self, url: str) -> Response:
        """Return the response for url, retrying transient failures (timeouts, 502, 503)
        with backoff based on observed latency. Raises Unavailable if the service stays down."""
    def with_timeout(self, seconds: float) -> "Http":
        """Copy of this client with a different overall deadline, for the rare slow endpoint."""
```

## 5. Special-general mixture (TypeScript)

Before: a general event bus knows about one feature.

```ts
class EventBus {
  publish(evt: Event) {
    if (evt.type === "cart.updated" && evt.payload.items.length === 0) this.analytics.trackEmptyCart();
    for (const h of this.handlers[evt.type] ?? []) h(evt);
  }
}
```

After: the bus stays a mechanism. The feature subscribes like any other user.

```ts
bus.subscribe("cart.updated", (e) => { if (e.payload.items.length === 0) analytics.trackEmptyCart(); });
```

## 6. General-purpose interface (Kotlin)

Before: the sheet model has one method per toolbar button, so UI ideas (the highlighted row, the "add below" button) leak into the data class. Every new button needs a new model method.

```kotlin
class Sheet {
    fun deleteHighlightedRow(highlight: Highlight) { ... }
    fun addRowBelowHighlight(highlight: Highlight) { ... }
    fun duplicateHighlightedRow(highlight: Highlight) { ... }
}
```

After: a few general operations on row ranges. The UI builds its buttons from them, and the model knows nothing about highlights.

```kotlin
/** A grid of cells. Rows are numbered from 0; row ranges are half-open [first, last). */
class Sheet {
    fun insertRows(before: Int, count: Int)        // clamps `before` to 0..rowCount
    fun deleteRows(first: Int, last: Int)          // an empty or out-of-range range does nothing
    fun copyRows(first: Int, last: Int, before: Int)
}
// UI: "add row below" = sheet.insertRows(highlight.row + 1, 1)
```

## 7. Splitting a function well (Go)

Splitting by line count produces conjoined helpers that pass state back and forth. Extract only a subtask that stands alone:

```go
// Good: parseDuration can be read and tested without knowing anything about loadConfig.
func loadConfig(path string) (Config, error) {
    // ... read file, walk keys ...
    timeout, err := parseDuration(raw["timeout"]) // general-purpose subtask
    // ...
}
```

If you cannot describe the extracted function without mentioning its caller, leave the code where it was.
