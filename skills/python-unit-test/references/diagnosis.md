# How `run` diagnoses a failure

The traceback is split into frames. If any frame is in the file under test, the error came from the code (`likely cause: code`), else from the test. Then the message is matched:

| Message contains | Likely cause | Suggested fix |
|---|---|---|
| TODO | test | finish the skeleton test |
| not raised | code | add the validation that raises, or fix the test input |
| ImportError / ModuleNotFoundError | setup | module name, package layout, installed dependency, circular import |
| wrong number of arguments / unexpected keyword | test or code | match the signature (update the test if the signature changed on purpose) |
| `NoneType` | code | return a value on every path, or guard `None` |
| ZeroDivisionError | code | check the divisor first |
| KeyError / IndexError | code | `.get()`, or check `len()` |
| AttributeError / NameError | code | spelling, type of the previous value, missing import |
| unsupported operand / not supported between | code | convert or validate types |
| FileNotFoundError / PermissionError | test | use `tempfile` or mock `open` |
| ConnectionError / timeout | test | mock the network call |
| RecursionError | code | fix the base case |
| AssertionError (values differ) | decide | read the intended behaviour, then fix the code or the expectation |

The rules are heuristics. Always read the code shown and confirm before proposing a change.

Source findings: PY001 mutable default, PY002 bare except, PY003 `== None`, PY004 swallowed exception, PY005 missing final return, PY006 `is` with a literal. Test findings: PT01 no assertion, PT02 empty, PT03 TODO, PT04 skipped, PT05 trivial assert.
