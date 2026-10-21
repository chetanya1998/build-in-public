# Build In Public brief · {{DAY}} · tinyinvoice

> **Demo.** This is a sample brief, written by hand for the demo's sample data so you can see the format. Your real brief is written by your own agent from `digest.md`, `trends.md` and your `narrative.md`, and its trend section links to real discussions from this week.

## Today in one line
Fixed the bug that made invoices look wrong about money: due dates that moved a day depending on where you live.

## What you shipped
- **Due dates no longer shift a day west of UTC.** Stored as calendar dates instead of timestamps, 6 new timezone tests, 1,382 old invoices migrated. *(Claude Code session 1, commit b1e8e15, log 10:25)*
- **No more dropped Stripe webhooks.** Events are saved first and retried at 1s, 4s and 16s. Replay test: 7 of 500 dropped before, 0 after. *(Codex session 1, commit 5ce850f, log 14:26)*
- **Onboarding went from 5 steps to 2.** New users finish by creating their first invoice from a sample client. *(Antigravity session, commit 018bcec, log 17:40)*

## The story
Two of today's three fixes were about trust, not features. A freelancer's invoice that shows the wrong due date, or stays "unpaid" after the client paid, makes the freelancer look careless in front of their client. The due-date bug is a classic: it only shows up west of UTC, and CI runs in UTC, so every test passed for months. This moves the arc from "it works" toward "you can rely on it", which is what the next milestone (100 paying users) needs.

## What people are talking about
*(In the demo there is no live trend scan. A real brief lists 3 to 5 discussions from `trends.md` and web search, each with a link and the line of today's work it connects to. For today's work it would look for things like:)*
- Discussions about timezone and date bugs, tied to the due-date fix.
- Threads about webhook reliability and idempotency, tied to the retry queue.
- Posts on shorter onboarding and time-to-first-value, tied to the 5 → 2 steps change.

## Post ideas
1. **"Our tests passed because CI lives in UTC"** · X thread · rides: timezone bug discussions · attach: a screenshot of the same invoice in UTC-10 and UTC+14 · *Why it works:* a specific, painful bug every developer recognises, with a one-line root cause and a lesson they can apply today.
2. **"7 of 500 payments were silently lost"** · LinkedIn · rides: webhook reliability threads · attach: before/after numbers · *Why it works:* a real number, and the stakes are money, which freelancers care about.
3. **"We deleted 3 onboarding steps"** · X single post · attach: `snapshots/demo-conv-onboarding-after.png` · *Why it works:* visual and quick to read. Best posted when you have the signup completion numbers.
4. **Weekly recap seed** · save for Sunday: "This week was about trust: dates, payments, first impressions."

## Ready-to-post drafts

### 1 · X thread
> Our invoices showed the wrong due date to every customer west of London, and every test passed.
>
> The bug: due dates were saved as midnight UTC, then shown in the viewer's timezone. Anyone west of London saw the day before.
>
> CI runs in UTC, so tests never saw it. Two customers did.
>
> The fix: a due date isn't a moment in time, it's a calendar date. Store "2026-11-01", not a timestamp. Format it with no timezone at all.
>
> Then a migration for the 1,382 invoices already saved the old way, and 6 tests that render the same invoice from UTC-10 to UTC+14.
>
> If you store dates people pick from a calendar, check yours. What's the worst timezone bug you've shipped?

**Single post (under 280):**
> Every test passed, and customers west of London still saw the wrong due date. CI runs in UTC; the bug only showed west of it. Fix: a due date is a calendar date, not a timestamp. Store "2026-11-01" and format it without a timezone.

### 2 · LinkedIn
> 7 out of 500 payments were silently ignored by our app.
> No error, no alert. The client paid, the invoice stayed "unpaid".
>
> Stripe sometimes sent the "paid" event a moment before our invoice was saved. We looked it up, found nothing, and replied "OK", so Stripe never tried again.
>
> Now every event is stored first and processed with retries. In a replay of 500 out-of-order events, dropped payments went from 7 to 0.
>
> If your app takes payments through webhooks, the question isn't whether this happens to you. It's whether you'd notice.
>
> I'm building Tinyinvoice in public. Follow along if you send invoices for a living.

*(Saved to `posts/{{DAY}}-x-utc-tests.md` and `posts/{{DAY}}-linkedin-lost-payments.md` in a real run.)*

## Capture tomorrow
- Signup completion rate for the new 2-step onboarding after a day of real users. That number turns idea 3 into a strong post.
- A side-by-side screenshot of the old 5-step and new 2-step onboarding.
