# Tool review checklist

Use this for a pull request that adds or changes agent tools.

## Per tool

- [ ] Name is `verb_noun`, unique, and could not be confused with another tool.
- [ ] Description says what it does, when to use it, when not to, what it returns and any side effects.
- [ ] Every parameter has a description; formats, units and defaults are stated.
- [ ] Closed sets of values use `enum`.
- [ ] Only truly necessary parameters are `required`.
- [ ] Output is compact, uses meaningful fields, and is paginated or truncated with a note.
- [ ] Errors explain the cause and the next step.
- [ ] Destructive or costly actions are labelled and are idempotent or confirmable.
- [ ] Inputs are validated server-side; the tool never trusts the model's arguments.

## Per tool set

- [ ] Each user-level job maps to one tool; no two tools do the same thing.
- [ ] Total tool count is as small as the jobs allow (aim for under 20 per agent).
- [ ] Tools from different systems are prefixed by domain.
- [ ] There is an eval set with requests that should and should not use each tool.

## Before and after

**Before**
```json
{"name": "get", "description": "Gets data",
 "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "t": {"type": "string"}}}}
```
Problems: vague name and description, no guidance on when to use it, unexplained `t`, internal `id` the model cannot know.

**After**
```json
{"name": "get_customer_orders",
 "description": "List a customer's recent orders with status and total. Use when the user asks about a customer's purchases, deliveries or refunds. Look the customer up by email; do not use for product stock (use check_stock). Returns up to 10 orders, newest first.",
 "inputSchema": {"type": "object",
   "properties": {
     "customer_email": {"type": "string", "format": "email", "description": "The customer's email address"},
     "status": {"type": "string", "enum": ["any", "pending", "shipped", "delivered", "refunded"], "description": "Filter by order status; default any"}},
   "required": ["customer_email"],
   "additionalProperties": false}}
```

## Error message pattern

```
<what failed>. <why, if known>. <what to try next>.
```
Example: `No orders found for ana@example.com in the last 90 days. Older orders are archived. Call search_archive with the same email to look further back.`
