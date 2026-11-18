# Handoff (2026-11-18)

## Goal
Add CSV export to the reports page, matching the existing PDF export options.

## Done
- `src/export.py`: `export()` writes CSV with a header row; unit tests pass.

## Decisions
- Use the standard `csv` module, not pandas: no new dependency (user agreed on 2026-11-18).

## Next step
Wire `export()` to the "Download CSV" button in the reports view.

## Open questions
None.

## Verify
`python -m unittest discover -s tests` (42 passed on 2026-11-18).
