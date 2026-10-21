### 10:25 - Due dates no longer shift a day in US timezones  (agent: claude)
- **What:** PDF invoices showed the due date one day early for anyone west of UTC. Fixed and migrated old invoices.
- **Why:** Two customers reported it. A wrong due date on an invoice looks like a mistake about money.
- **How:** Store due dates as calendar dates (YYYY-MM-DD) instead of UTC-midnight timestamps, and format them with no timezone conversion.
- **Struggle:** It only happened west of UTC, and our CI runs in UTC, so every test passed.
- **Result:** 6 new tests across UTC-10 to UTC+14. 1,382 existing invoices migrated.
- **Files:** src/lib/dates.ts, src/pdf/render.ts, migrations/0007_due_date_as_date.sql
- **Tags:** #war-story #lesson #metric

### 14:26 - No more dropped Stripe webhooks  (agent: codex)
- **What:** Webhooks that arrive before the invoice exists are now stored and retried instead of dropped.
- **Why:** A dropped `invoice.paid` event means an invoice stays "unpaid" after the client paid.
- **How:** Save every event to a webhook_events table first, then process it with retries at 1s, 4s and 16s.
- **Struggle:** The handler returned 200 even on failure, so Stripe never retried on its own.
- **Result:** Replay test with 500 out-of-order events: 7 dropped before, 0 after.
- **Files:** src/webhooks/stripe.ts, src/webhooks/queue.ts
- **Tags:** #metric #decision

### 17:40 - Onboarding from 5 steps to 2  (agent: antigravity)
- **What:** New users now finish onboarding by creating their first invoice from a sample client.
- **Why:** Most people who left during signup left on the tax settings step.
- **How:** Default tax settings by country, and move the logo upload to Settings.
- **Result:** 5 steps → 2. Screenshot saved as onboarding-after.png.
- **Files:** src/onboarding/*
- **Tags:** #visual #decision
