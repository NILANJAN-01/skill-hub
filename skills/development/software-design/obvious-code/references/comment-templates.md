# Interface comment templates

Use the project's existing doc style first. These templates show *what* to include: behaviour for callers, each argument with meaning, units and range, the result, side effects, errors, preconditions. They leave out how it works.

## Python (docstring)

```python
def reserve(sku: str, quantity: int, hold_for: timedelta = timedelta(minutes=15)) -> Reservation:
    """Hold stock for a customer's cart so it cannot be sold to someone else.

    Args:
        sku: Stock-keeping unit, as printed on the shelf label.
        quantity: Units to hold; must be at least 1.
        hold_for: How long the hold lasts before the units return to stock.

    Returns:
        The reservation; pass its id to `confirm` or `release`.

    Raises:
        OutOfStock: fewer than `quantity` units are free. Nothing is held.

    Side effects:
        Free stock for `sku` drops by `quantity` until the hold is confirmed, released or expires.
    """
```

Class:

```python
class RateLimiter:
    """Limits how often each client may call an API: at most `rate` calls per second,
    with bursts up to `burst`. One instance is shared by all request threads (thread-safe).
    Limits reset when the process restarts; they are not shared between servers."""
```

## Java (Javadoc)

```java
/**
 * Moves money between two accounts of the same customer.
 *
 * <p>The transfer is atomic: either both balances change or neither does.
 *
 * @param from   account to debit; must belong to {@code customerId}
 * @param to     account to credit; may equal {@code from}, in which case nothing happens
 * @param amount positive amount in the accounts' currency, at most two decimal places
 * @return the transfer record, already committed
 * @throws InsufficientFunds if {@code from} would go below its overdraft limit; nothing changes
 */
public Transfer move(AccountId from, AccountId to, BigDecimal amount) { ... }
```

## TypeScript / JavaScript (JSDoc / TSDoc)

```ts
/**
 * Resolves a short link to its target URL and records one visit.
 *
 * @param code - The part after the domain, case-insensitive (for example "x7Kp").
 * @returns The target URL, or `undefined` for unknown or expired codes (no error is thrown).
 * @remarks Visits are counted asynchronously; counts may lag by a few seconds.
 */
export async function resolve(code: string): Promise<string | undefined> { ... }
```

## Kotlin (KDoc)

```kotlin
/**
 * Returns the delivery slots still bookable on [day] for [postcode], earliest first.
 * Slots already full are left out. An unknown postcode gives an empty list.
 *
 * @param day local date in the warehouse's time zone
 */
fun openSlots(day: LocalDate, postcode: String): List<Slot>
```

## Go

Go doc comments start with the name and are full sentences:

```go
// Debounce returns a function that calls fn only after it has not been called for wait.
// Calls during the wait restart the timer. The returned function is safe for concurrent use;
// fn runs on its own goroutine.
func Debounce(wait time.Duration, fn func()) func() { ... }
```

## C# (XML docs)

```csharp
/// <summary>Finds customers whose name contains <paramref name="text"/>, ignoring case and accents.</summary>
/// <param name="text">At least 2 characters; shorter input returns an empty list.</param>
/// <param name="limit">Maximum results, 1-100.</param>
/// <returns>Matches ordered by most recent order first.</returns>
public IReadOnlyList<Customer> Search(string text, int limit = 20) { ... }
```

## Rust

```rust
/// Parses a duration like `"1h30m"` or `"45s"`.
///
/// Units: `h`, `m`, `s`, `ms`. Whitespace is not allowed.
///
/// # Errors
/// Returns `ParseError::UnknownUnit` for any other suffix and `ParseError::Empty` for `""`.
pub fn parse_duration(text: &str) -> Result<Duration, ParseError> { ... }
```

## Member (field) comments

```python
# Bytes of the current response already written to the socket; never more than len(self._body).
self._sent = 0

# Maps a product id to the number of units in open carts. A product with none is absent, not 0.
self._held_units: dict[str, int] = {}
```

## Implementation comments

```python
# Group lines by invoice first: a refund can only be matched against lines of the same invoice.
by_invoice = group_by(lines, key=lambda line: line.invoice_id)

# Each pass removes the cheapest matching line, so partial refunds consume low-value items first
# (finance rule FIN-112).
for invoice_id, invoice_lines in by_invoice.items():
    ...
```

## Before and after

| Before (repeats the code) | After (adds information) |
|---|---|
| `// increment i` | (delete it) |
| `/** Gets the timeout. */ int getTimeout()` | `/** Seconds to wait for the first byte before giving up; 0 means wait forever. */` |
| `# loop over users` | `# Notify only users who opted in since the last digest; others get the weekly summary.` |
| `// set flag` | `// Stop accepting new jobs; jobs already queued still run (drain mode).` |
