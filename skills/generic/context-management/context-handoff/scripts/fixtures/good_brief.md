## Goal
Find why `GET /reports` takes over 2 seconds.

## Context
The endpoint is in `api/reports.py`; it was fast before the 2026-11-10 release.

## Constraints
Read-only: do not change code or data.

## Done when
You can name the slow query or call and show its timing.

## Return
At most 10 lines: the cause, the evidence (file:line, timing) and one suggested fix.
