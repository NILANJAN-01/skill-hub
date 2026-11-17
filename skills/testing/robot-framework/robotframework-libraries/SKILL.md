---
name: robotframework-libraries
description: "Write Python keyword libraries for Robot Framework with the current API: @library and @keyword, type hints and argument conversion (Literal, enums, TypedDict, custom converters, Secret, Python 3.12 type aliases), embedded arguments, async keywords, logging, listeners, and Libdoc docs in Markdown. A script reviews a library. Use when creating or reviewing custom Robot Framework libraries."
license: MIT
compatibility: The review script needs Python 3.8+ (standard library only). Libraries target Robot Framework 7.x; Secret needs 7.4+, Markdown Libdoc and type aliases 7.5+.
metadata:
  title: "Robot Framework libraries: Python keywords done right"
  category: robotframework-tools
---

# Robot Framework keyword libraries

When the standard and community libraries do not cover a system (an internal API, a device, a database helper), write a small Python library. Good libraries have typed arguments (so RF converts values), clear docs (so Libdoc and IDEs show them), safe logging, and the right scope.

## When to use

- Create a library for a company system, or wrap a Python SDK as keywords.
- Review or modernise an existing library (types, docs, deprecated `robot.utils` helpers).
- Add listeners or a library that reacts to test events.

## When NOT to use

- Writing `.robot` suites and user keywords: use `robotframework-test-authoring`.
- A ready library exists (Browser, SeleniumLibrary, RequestsLibrary, DatabaseLibrary, AppiumLibrary): use it instead of writing one.

## Procedure

1. **Shape the library** ([references/library-api.md](references/library-api.md) has full examples):
   ```python
   from enum import Enum
   from typing import Literal
   from robot.api import logger
   from robot.api.deco import keyword, library
   from robot.api.types import Secret            # RF 7.4+

   class Env(Enum):
       STAGING = "staging"
       PROD = "prod"

   @library(scope="SUITE", version="1.2.0", doc_format="Markdown")   # Markdown docs: RF 7.5+
   class OrdersLibrary:
       """Keywords for the Orders API.

       Connect first with `Connect To Orders API`.
       """

       def __init__(self, base_url: str = "https://staging.example.com"):
           self._base_url = base_url
           self._session = None

       @keyword
       def connect_to_orders_api(self, user: str, token: Secret, env: Env = Env.STAGING):
           """Open an authenticated session.

           Args:
               user: Service account name.
               token: API token; pass a Secret variable, it is never logged.
               env: Target environment.
           """
           self._session = make_session(self._base_url, user, token.value)
           logger.info(f"Connected to {env.value} as {user}")

       @keyword("Order ${order_id: int} should have status ${status}")
       def order_should_have_status(self, order_id: int, status: Literal["NEW", "PAID", "SHIPPED"]):
           """Fail unless the order has the expected status."""
           actual = self._session.get(f"/orders/{order_id}").json()["status"]
           if actual != status:
               raise AssertionError(f"Order {order_id} is {actual}, expected {status}")
   ```
2. **Rules that pay off:**
   - Keyword names are readable sentences; use `@keyword("...")` for embedded arguments.
   - Type hints on every argument: RF converts `"42"` → `int`, `"PAID"` → `Literal`, `"staging"` → `Enum`, JSON-like strings → `list`/`dict`/`TypedDict`, `"30s"` → `timedelta`. Python 3.12 `type Locator = str | list[str]` aliases are understood (RF 7.5).
   - Credentials are `Secret` (RF 7.4+): the keyword receives a `Secret`, uses `.value` only where needed, and never logs it. Use `str | Secret` to accept both during a migration.
   - Raise `AssertionError` with a clear message for verification failures; other exceptions mean "error".
   - Log with `robot.api.logger` (`info`, `debug`, `warn`, `console`), not `print`.
   - Scope: `GLOBAL` for shared clients and connections, `SUITE` for per-suite state, `TEST` (default) for a fresh instance per test.
   - Docstrings: Google style `Args:` / `Returns:` / `Raises:` sections are rendered by Libdoc (RF 7.5).
3. **Review it:**
   ```bash
   python scripts/rf_lib_lint.py libraries/OrdersLibrary.py
   python scripts/rf_lib_lint.py libraries/ --json
   ```
   It lists the keywords found and flags missing docstrings and type hints, secret-like arguments not typed `Secret`, `print()` instead of the logger, class libraries without an explicit scope, `BuiltIn().get_variable_value(..., default=...)` (positional-only since 7.4), and deprecated `robot.utils` helpers (`is_string`, `is_integer`, `ET`, ...; removal planned).
4. **Document it:**
   ```bash
   libdoc libraries/OrdersLibrary.py docs/OrdersLibrary.html
   libdoc libraries/OrdersLibrary.py docs/OrdersLibrary.md        # Markdown output, RF 7.5
   libdoc libraries/OrdersLibrary.py show                          # print docs in the console (Markdown)
   libdoc --format json libraries/OrdersLibrary.py spec.json        # spec for IDEs and tooling
   ```
   Markdown documentation needs `pip install markdown pygments`.
5. **Test it:** unit-test the Python code with pytest (mock the system), then `robot --dryrun` a suite that imports the library, then a real run.

## Safety rules

- Never log secrets or full request bodies that contain them; accept credentials as `Secret`.
- Do not catch `BaseException`: since RF 7.5 timeouts (`TimeoutExceeded`) derive from it so that `except Exception` does not swallow them; clean up in `finally`.
- Keep side effects explicit in keyword names (`Delete Order`, not `Check Order`).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No keyword with name ...` but the method exists | With `@library`, only `@keyword` methods are keywords unless `auto_keywords=True`; private methods (`_x`) are never keywords. The review script lists such methods as `not-exposed` |
| Argument arrives as a string | Add a type hint; RF converts based on it |
| `ValueError: Argument 'x' got value '...' that cannot be converted to ...` | The value does not match the type; check the type hint or pass a variable of the right type |
| `get_variable_value() got an unexpected keyword argument 'default'` | RF 7.4 made BuiltIn arguments positional-only: pass the default positionally |
| Libdoc ignores Markdown | Set `doc_format="Markdown"` (or `ROBOT_LIBRARY_DOC_FORMAT`) and install `markdown` |

## References

- [references/library-api.md](references/library-api.md): static, dynamic and hybrid APIs, converters, listeners v3, async keywords, timeouts and the 7.x changes for library authors.
