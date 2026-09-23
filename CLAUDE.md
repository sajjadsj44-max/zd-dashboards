# Working preferences (Sajjad)

- Work autonomously: make the reasonable call yourself instead of stopping to ask for
  confirmation, and proceed straight through to commit + push.
- Only ask a clarifying question when genuinely blocked (e.g. a fact you cannot find
  anywhere and guessing wrong would break something — verify with the user first,
  don't invent it).
- After committing and pushing a change, always open a pull request into `main`
  (or merge to `main` directly if a PR isn't possible) — do this automatically,
  without asking or waiting to be told each time.

# Rate data rules

- Every rate filled into the Rate Analysis library must name its reference source
  and date in the Source / remarks column, in the form
  `<source>, DD-Mon-YYYY — <details>` (e.g. `Phoenix GRN RCP-312, 30-Aug-2026 — M/S Hamza Steel`).
  The Effective date column must carry the same date.
- No dated source → leave the rate at 0 or mark it `ASSUMPTION — no dated source`.
  Never invent a rate.
- Prefer a current (last ~30 days) dated Lahore market rate; if none can be
  found, use the latest Phoenix GRN rate and say so in the remarks.
