# Writing good Python unit tests

- **Name** tests `test_<function>_<situation>` so they link to the function and read like a spec.
- **One behaviour per test.** Arrange, act, assert.
- **Cover per function:** typical input; empty/`None`/zero/negative/boundary values; every `raise` in the body; every branch (`if`, loops that run 0, 1 and many times).
- **Assert something that can fail:** `assertEqual(result, expected)`, `assertRaises(ValueError)`, state changes on the object. Not just "it didn't crash".
- **Isolate:** `unittest.mock.patch("module.name")` patches where the name is *used*. Use `tempfile.TemporaryDirectory()` for files, a fixed value for time and randomness.
- **Classes:** build the object in `setUp`, test each method, and test state across calls (`add(2)` then `add(3)` gives 5).
- **Floats:** `assertAlmostEqual`. **Async:** `unittest.IsolatedAsyncioTestCase`.
- **Bugs found by a test:** keep the test, fix the code. A failing test that shows a real bug is a success.
- **Stay compatible:** prefer `unittest.TestCase` classes. They run with pytest and without it.
