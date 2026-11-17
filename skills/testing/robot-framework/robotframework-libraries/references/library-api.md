# Library API reference

User Guide, "Creating test libraries": https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#creating-test-libraries

## Library shapes

| Shape | When | How |
|---|---|---|
| Module | A few stateless keywords | Public functions in `MyLib.py` are keywords; `Library    MyLib.py` |
| Class (static API) | State, configuration, connections | Class with the same name as the module, or `@library`; public methods are keywords |
| Dynamic API | Keywords generated at run time (from an API spec, a remote system) | `get_keyword_names()` and `run_keyword(name, args, kwargs)`; optional `get_keyword_documentation`, `get_keyword_arguments`, `get_keyword_types` |
| Hybrid API | Generated keywords that are still real Python callables | `get_keyword_names()` returning method names; RF calls the attributes directly |

`@library` options: `scope="GLOBAL"|"SUITE"|"TEST"`, `version`, `doc_format="ROBOT"|"HTML"|"TEXT"|"reST"|"Markdown"` (Markdown: 7.5), `listener`, `converters`, `auto_keywords` (default **False** with `@library`: only `@keyword` methods become keywords; set `True` to expose every public method). A plain class or module without `@library` exposes all public methods/functions, unless some use `@keyword`. Since 7.2, a class with `@library` is recognised whatever its name.

## Argument conversion

Supported hints include `int`, `float`, `Decimal`, `bool`, `str`, `bytes`, `bytearray`, `datetime`, `date`, `timedelta`, `Path`, `Enum`, `Flag`, `Literal[...]`, `list[int]`, `dict[str, int]`, `tuple`, `set`, `TypedDict`, `Union`/`X | Y`, `None`, `Any`, `object`. Stringified hints (`'list[int]'`) work. Recent changes:

- 7.4: `bytes`/`bytearray` accept integers or lists of integers; `str` arguments receive bytes as code points; any sequence literal converts to `list`/`tuple`/`set`; `object` is a no-op (defaults no longer drive conversion; use `int | object = 1` if you relied on it).
- 7.4: `robot.api.types.Secret`, plus `KeywordName` / `KeywordArgument` for keywords that run other keywords (like `Run Keyword`).
- 7.5: Python 3.12 `type` aliases (`type ID = int`) are converted as the underlying type.

Custom converters:
```python
from datetime import date
from robot.api.deco import library

def parse_fi_date(value: str) -> date:          # "17.11.2026"
    d, m, y = value.split(".")
    return date(int(y), int(m), int(d))

@library(converters={date: parse_fi_date})
class Calendar:
    def event_should_be_on(self, day: date): ...
```

## Embedded and mixed arguments

```python
@keyword("Add ${quantity: int} ${product} to cart")         # typed embedded args (7.3)
def add_to_cart(self, quantity: int, product: str): ...

@keyword("Number of ${animals} should be")                  # mixed embedded + normal (7.0)
def animal_count(self, animals: str, count: int): ...       # Number of horses should be    count=2
```

## Secrets

```python
from robot.api.types import Secret

@keyword
def log_in(self, user: str, password: Secret):
    self._client.login(user, password.value)        # .value only at the point of use
```
`str(secret)` is `<secret>`, so accidental logging is safe. Accept `str | Secret` while callers migrate.

## Logging

```python
from robot.api import logger
logger.info("Order created")                 # log file
logger.debug("payload: ...")                 # visible with --loglevel DEBUG
logger.warn("Deprecated endpoint used")      # log + console warnings
logger.console("Progress 3/10")              # console only
logger.info("<b>bold</b>", html=True)
```
Since 7.4 libraries can log errors and warnings to the log file only (see the User Guide's logging section).

## Listeners (v3 is the default since 7.0)

```python
class Timing:
    ROBOT_LISTENER_API_VERSION = 3

    def start_test(self, data, result): ...
    def end_test(self, data, result):
        if result.failed:
            result.message += " (see screenshot)"
    def start_keyword(self, data, result): ...          # 7.0: keywords and control structures
    def end_library_keyword(self, data, implementation, result): ...
```
Run with `robot --listener Timing.py tests/`, or attach to a library with `@library(listener=Timing())`. Since 7.2 listeners are also told about keywords they start themselves: guard against recursion. To skip a test dynamically, change the `result` tags, not `data` (7.2).

Custom console output (7.5): a listener-style class passed with `--console` replaces the normal console logger (also for `rebot`).

## Async keywords

`async def` keywords run on RF's event loop (since 6.1; dynamic and hybrid libraries since 7.0):
```python
@keyword
async def wait_for_event(self, name: str, timeout: float = 10): ...
```

## Timeouts

Test and keyword timeouts raise `robot.errors.TimeoutExceeded`. Since 7.5 it derives from `BaseException`, so `except Exception` no longer swallows it; release resources in `finally`. Since 7.3 library keywords can clean up when a timeout occurs, and `BuiltIn().run_keyword` pauses the timeout.

## Deprecated helpers to replace

| Deprecated | Use instead | Since |
|---|---|---|
| `robot.utils.is_string`, `is_bytes`, `is_number`, `is_integer`, `is_pathlike` | `isinstance(...)` | 7.3 |
| `robot.utils.ET` | `xml.etree.ElementTree` | 7.3 |
| `robot.utils.read_rest_data`, `split_tags_from_doc`, `is_union` | standard library / your own code | 7.5 |
| `BuiltIn().get_variable_value("${x}", default=...)` | positional default | 7.4 |
| Arguments `list_` (Collections), `time_` (BuiltIn) when called by name | `list`, `time` | renamed in 8.0 |

## Libdoc

```bash
libdoc MyLib.py MyLib.html                 # HTML (rewritten in 7.2)
libdoc MyLib.py MyLib.md                   # Markdown (7.5)
libdoc MyLib.py show                       # console, Markdown (7.5)
libdoc MyLib.py show "Keyword Name"
libdoc --format json MyLib.py MyLib.json   # machine-readable spec
libdoc --spec-doc-format raw ...           # keep docs as written in spec files
```
Markdown docs support links like `[Keyword Name]` and `[introduction]` to keywords, sections and types.
