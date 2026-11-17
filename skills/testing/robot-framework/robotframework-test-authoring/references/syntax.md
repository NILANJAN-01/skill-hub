# Robot Framework syntax reference (7.x)

User Guide: https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html
Release notes: https://github.com/robotframework/robotframework/tree/master/doc/releasenotes

## A complete suite

```robotframework
*** Settings ***
Documentation       Checkout flows for registered customers.
Library             Browser    timeout=10s
Resource            ../resources/shop.resource
Suite Setup         Open Shop
Suite Teardown      Close Browser    ALL
Test Tags           checkout    web

*** Variables ***
${BASE_URL}                 %{BASE_URL=https://staging.example.com}
${USER}                     %{E2E_USER}
${PASSWORD: Secret}         %{E2E_PASSWORD}                 # 7.4+: never a literal
${TIMEOUT: timedelta}       30s                             # 7.3+: typed variables
@{PAYMENT_METHODS}          card    invoice    paypal

*** Test Cases ***
Registered Customer Can Pay By Card
    [Documentation]    Happy path with a saved card.
    [Tags]    smoke
    [Metadata]    Issue    SHOP-1234                         # 7.5+
    GROUP    Fill the cart                                   # 7.2+
        Log In As    ${USER}    ${PASSWORD}
        Add Product To Cart    Robot T-shirt    quantity=2
    END
    GROUP    Pay
        Pay With    card
        Order Confirmation Should Be Shown
    END

Every Payment Method Is Offered
    [Template]    Payment Method Should Be Available
    FOR    ${method}    IN    @{PAYMENT_METHODS}
        ${method}
    END
```

## Resource file with user keywords

```robotframework
*** Settings ***
Library    Browser

*** Keywords ***
Open Shop
    New Browser    chromium    headless=${TRUE}
    New Context    viewport={'width': 1280, 'height': 800}
    New Page    ${BASE_URL}

Log In As
    [Arguments]    ${user}    ${password: Secret}               # typed arguments, 7.3+
    [Setup]    Go To    ${BASE_URL}/login                     # keyword setup, 7.0+
    Fill Text    id=email    ${user}
    Fill Secret    id=password    $password                   # Browser: typed without logging (check your Browser version accepts RF 7.4 Secret values)
    Click    role=button[name="Sign in"]
    Get Text    h1    ==    Dashboard                         # Browser assertion with retry

Add Product To Cart
    [Arguments]    ${name}    ${quantity: int}=1
    Click    text=${name}
    Fill Text    id=qty    ${quantity}
    Click    role=button[name="Add to cart"]

Total Should Be
    [Arguments]    ${expected: float}
    ${text}=    Get Text    id=total
    VAR    ${total: float}    ${text.strip('$')}
    Should Be Equal    ${total}    ${expected}
    RETURN    ${total}
```

## Variables

```robotframework
VAR    ${name}    value                        # local
VAR    ${shared}    value    scope=SUITE       # TEST, SUITE, SUITES, GLOBAL
VAR    @{list}    a    b    c
VAR    &{dict}    key=value    other=item
VAR    ${count: int}    42                     # typed (7.3+)
VAR    ${empty}    ${EMPTY}    scope=SUITE     # 7.4: a non-local VAR needs an explicit value
```

Typed forms (7.3+): `${x: int}`, `${ids: list[int]}`, `@{nums: int}` (item type), `&{dates: date}` (value type), `&{map: int=float}` (key=value types), `${dir: Literal["UP", "DOWN"]}`, `${n: int | float}`. Embedded arguments too: `Move ${distance: int} meters`.

Command line: `--variable "ITERATIONS: int:99"`, `--variable "START: datetime:now"`, `--variable "PASSWORD: Secret:$PASSWORD"` (7.4).

Secrets (7.4+): `${TOKEN: Secret}    %{API_TOKEN}`; joined values are allowed (`${HDR: Secret}    Bearer ${TOKEN}`); literals are rejected. Keywords declare `token: Secret` (or `str | Secret`) in Python.

## Control structures

```robotframework
IF    ${status} == 200
    Log    ok
ELSE IF    ${status} == 404
    Fail    Not found
ELSE
    Fail    Unexpected ${status}
END

IF    ${debug}    Log    verbose details           # inline IF
${label}=    IF    ${n} > 1    Set Variable    items    ELSE    Set Variable    item

TRY
    Click    id=cookie-accept
EXCEPT    *TimeoutError*    type=GLOB
    Log    No cookie banner
FINALLY
    Take Screenshot
END

WHILE    ${retries} > 0    limit=10
    ${retries}=    Evaluate    ${retries} - 1
    IF    ${done}    BREAK
END

FOR    ${index}    ${item}    IN ENUMERATE    @{items}    start=1
    IF    $item == 'skip'    CONTINUE
    Log    ${index}: ${item}
END
FOR    ${a}    ${b}    IN ZIP    ${list1}    ${list2}    mode=STRICT
    Log    ${a} ${b}
END
```

## Test metadata, tags, templates

- `[Metadata]    Name    value` on tests and tasks (7.5+); suite metadata with `Metadata` in Settings.
- `Test Tags` in Settings, `[Tags]` per test; remove an inherited tag with `-tag` (`[Tags]    -slow`); a literal tag starting with `-` is written `\-tag`.
- Tag patterns on the command line: `--include "smoke AND web"`, `--exclude "slow OR flaky"`, `NOT`; the forms `XORY` and `&` are deprecated (7.5).
- Templates: `[Template]    Keyword` per test or `Test Template` per suite; templated tests run every iteration even after a SKIP (7.2).

## Tests in Markdown (7.5+)

````markdown
# Login

Customers sign in with email and password.

```robotframework
*** Test Cases ***
Valid Login
    Log In As    ${USER}    ${PASSWORD}
```
````

Save as `login.robot.md` (parsed automatically), or include other `*.md` with `--parseinclude` / `--extension`.

## Project layout that scales

```
tests/                 suites by feature (checkout/, account/), one behaviour per test
resources/             *.resource: user keywords, page/screen keywords, no tests
libraries/             Python keyword libraries (see robotframework-libraries)
variables/             per-environment variable files (staging.py, prod_readonly.py)
results/               output (git-ignored)
requirements.txt       pinned robotframework and library versions
pyproject.toml         [tool.robocop.*] settings
```
Select an environment with `--variablefile variables/staging.py`, never by editing tests.

## What changed in 7.0 – 7.5

| Version | New | Removed / deprecated / changed |
|---|---|---|
| 7.0 | `VAR`, keyword `[Setup]`, mixed embedded + normal arguments, listener v3 for keywords, JSON results (`rebot --output output.json`), `Literal` conversion, dark mode logs | Python 3.6/3.7 dropped; output.xml timestamps ISO 8601 (`start`/`elapsed`); `--test` and `--include` are cumulative; `--suite` needs the full name; `[Return]` deprecated (use `RETURN`) |
| 7.1 | Listener and result-model improvements | – |
| 7.2 | `GROUP`, JSON output from `robot --output output.json`, new Libdoc HTML | Templated tests run all iterations after SKIP; listener-related model changes |
| 7.3 | Typed variables `${x: type}` in data and `--variable "X: int:1"`, timeout handling fixes, Process kills child on timeout | Variables with `: ` in the name clash with typing |
| 7.4 | `Secret` variables, typed standard-library keywords, better bytes handling, collapsible errors in logs, env vars in argument files | `VAR` without value in non-local scope, `NO VALUES`, OperatingSystem `Run`/`Run And Return RC(And Output)` (use Process) deprecated; BuiltIn arguments positional-only in Python |
| 7.5 | `[Metadata]` for tests, `*.robot.md` tests, Libdoc Markdown docs/output (`libdoc X show`), custom console loggers (`--console`), Python 3.12 `type` aliases | Testdoc and Telnet library deprecated (external packages; the built-in Telnet library cannot import on Python 3.13+, where `telnetlib` was removed); tag patterns `XORY` / `&` deprecated; `TimeoutExceeded` is a `BaseException`; Python 3.15 supported |

Robot Framework 8.0 is announced to rename `list_` (Collections) and `time_` (BuiltIn) arguments to `list` and `time`, and to make deprecation warnings more visible.
