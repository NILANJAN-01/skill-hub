# Naming checklist

Ask of every new name: *if someone saw only this name, with no declaration, comment or surrounding code, how close would their guess be?*

## Checklist

- [ ] It says what the thing **is** (or, for a function, what it **does or returns**), not how it is stored.
- [ ] It is specific enough to rule out the wrong meaning: `deadlineUtc`, not `time`.
- [ ] Units are in the name or the comment: `timeoutMs`, `distanceKm`, `sizeBytes`.
- [ ] Booleans read as true/false statements: `isEmpty`, `hasErrors`, `shouldRetry`, `paymentCaptured`.
- [ ] Collections are plural or describe the grouping: `pendingOrders`, `ordersByCustomer`.
- [ ] One concept has one name across the code base. Different concepts never share a name.
- [ ] It follows the project's casing and prefix conventions.
- [ ] Two or three words are enough. If you need more, the thing may be doing too much.

## Vague to precise

| Vague | Why | Better |
|---|---|---|
| `data`, `info`, `obj`, `item` | Could be anything | `invoiceLines`, `customerProfile` |
| `tmp`, `temp`, `x2` | Says only that it is short-lived | `unsavedDraft`, `previousBalance` |
| `count`, `getCount()` | Count of what? | `openTicketCount`, `numRetries` |
| `status`, `flag`, `mode` (boolean) | What does `true` mean? | `isArchived`, `syncEnabled` |
| `result` (function returns nothing) | Misleads: looks like a return value | `mergedSettings` |
| `handle()`, `process()`, `doWork()` | Says nothing about the effect | `retryFailedPayments()`, `renderInvoicePdf()` |
| `Manager`, `Helper`, `Util` classes | A bag of unrelated functions | Name the abstraction: `PriceCalculator`, `SessionStore` |
| `id` for two kinds of id | Leads to mixing them up | `userId`, `accountId` |
| `list`, `map`, `str` | Names the type, not the meaning | `blockedDomains`, `priceBySku` |

## When short names are fine

- Loop indexes and lambdas whose whole scope is visible: `for i in range(n)`, `xs.map(x => x * 2)`.
- Well-known conventions in the domain: `ctx` for a context object, `err` in Go, `T` for a type parameter.

## When you cannot find a good name

Difficulty naming something is a design signal. The entity may combine unrelated responsibilities, or its purpose may not be clear yet. Write its interface comment; if that is also hard, revisit the design (`deep-modules`, `design-it-twice`).
