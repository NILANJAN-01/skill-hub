# annotations.json

`analyze` writes this file with `TODO(architecture)` markers and keeps your text when it runs again (for components, flows and dismissals whose ids still exist). `render` turns it, with `model.json`, into `ARCHITECTURE.md`.

```json
{
  "summary": "Order service for the web shop: a FastAPI app that prices carts, stores orders in PostgreSQL and publishes events to Kafka. Built with Poetry, shipped as a Docker image.",
  "components": {
    "src/api":  {"title": "HTTP API", "description": "FastAPI routes; validates input and calls core. The only code that knows about HTTP."},
    "src/core": {"title": "", "description": "Pricing and validation rules. No I/O of its own: talks to storage through repository interfaces."}
  },
  "flows": {
    "src/api/routes.py:create_order()": "POST /orders: validates the cart, prices it in core, saves it and publishes OrderCreated."
  },
  "extra_flows": [
    {"title": "Nightly report (cron)", "steps": ["jobs/report.py `main` loads yesterday's orders", "core/stats.py `summarize` totals them", "the CSV is uploaded to S3"]}
  ],
  "notes": [
    "The payment client is chosen by name from config, so no arrow points to it.",
    "Inferred, not read: retries are handled by the Kafka consumer group."
  ],
  "dismissed": {
    "SEC009@src/db/report.py:41": "Query text is a constant; no outside input reaches it.",
    "COD005": "TODOs are tracked in the issue tracker."
  }
}
```

Rules:

1. **Component descriptions** say what the part does and why it exists, and who calls it. "Contains utility functions" is not a description. `title` (optional, a few words) replaces the language and size line in the HLD box.
2. **Flow keys** are the keys already in the file (`file:entry()`); write what the flow does from the code you read, and what it misses (a callback, a queue, a network hop).
3. **extra_flows** describe flows the script could not trace (dynamic wiring, jobs, message handlers). Each step names a component and, where it helps, a file and function you read.
4. **notes** cover what the diagrams cannot show. Mark guesses as guesses.
5. **dismissed** keys are a rule (`COD005`), a rule in a file (`SEC004@tools/build.py`) or one finding (`SEC009@src/db.py:41`). The value is the reason; it is printed in the audit.
6. Only ids that exist in `model.json` are used. Unknown ids are ignored.
