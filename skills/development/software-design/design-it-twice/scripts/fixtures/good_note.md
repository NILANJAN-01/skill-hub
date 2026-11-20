# Design: retries in the HTTP client

## Problem
Service code calls `client.get(url)` and today handles timeouts itself, in 14 places.
Callers are request handlers that want a response or a clear failure.

## Constraints and non-goals
Must not retry non-idempotent requests. Not a circuit breaker.

## Alternative A: per-call retry options

### Interface sketch
```
get(url, retries=3, backoff_ms=200, retry_on=(502, 503))
```

### How a caller uses it
```
page = client.get(url, retries=5, backoff_ms=100)
```

### Hides
The sleep loop.

### Pros
- Explicit; each caller can tune.

### Cons
- Every caller must choose numbers it cannot know; 14 call sites to keep in step.

## Alternative B: client-owned retry policy

### Interface sketch
```
class HttpClient:
    def __init__(self, base_url)
    def fetch(self, url) -> Response   # raises Unavailable after retries
```

### How a caller uses it
```
page = client.fetch(url)
```

### Hides
Which status codes are retried, backoff computed from observed latency, idempotency rules.

### Pros
- Common case is one call; policy lives in one place.

### Cons
- Callers cannot tune per call (rarely needed; a separate method can be added later).

## Comparison

| Question | A | B |
|---|---|---|
| Simplest interface for the common case? | no | yes |
| General enough? | yes | yes |
| What leaks? | retry policy | nothing |
| Errors callers handle | timeouts, 5xx | Unavailable only |
| Critical path cost | same | same |

## Decision
Chosen: B
Why: the policy is knowledge only the client has; A pushes it into 14 callers.

## Interface comments (write before the code)
```
fetch(url): Return the response for an idempotent GET. Transient failures
(timeouts, 502, 503) are retried internally; raises Unavailable when the
service stays down for the whole retry budget.
```

## Red-flag review
- [x] Shallow module
- [x] Information leakage
- [ ] Temporal decomposition n/a: single step
- [x] Overexposure
- [x] Pass-through methods or variables
- [x] Special-general mixture
- [x] Errors pushed to callers
- [x] Hard to name or describe
