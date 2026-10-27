# Supporting OurHike — pay what you want, $0 included

**#1876 — Ask every hiker to choose what they give after their fifth day of use, $0 included, and take payment only on the website.** This file is the one home for the decisions; the code carries the mechanism and points here. Every decision below was made by the maintainer by poll on 2026-10-23 (and one on 2026-10-24), each answered against a drawn mock or a real screenshot in session.

Companion to [PRICING_MODEL.md](PRICING_MODEL.md), whose 2026-08-27 rule "money never passes through OurHike" this **supersedes in part**: OurHike now takes support for its **own** costs. Its pricing values #1–#5 stand untouched, and value #1 above all — nothing safety-relevant is ever behind a payment.

---

## 1. Where the money goes, in the founder's words

- **Running costs first**, then **growth** — marketing and promotion — with anything beyond running costs.
- **None of it is the founder's personal income.**
- **At most 3% to paying developers**, ever, and only if OurHike grows to a venture-backed app's scale and has to pay them.
- **The long-term intent is money flowing from OurHike to the member clubs that maintain the trail.** That starts at the nonprofit stage (§2), not before. The direct "give to the club on its own site" links stay exactly as they were, and nothing a hiker gives a club passes through OurHike.

The public reading is [`site/src/pages/support.astro`](../site/src/pages/support.astro) (`ourhike.org/support/`), rewritten for this as the pay-what-you-want page.

## 2. How it is held: now, next, later

| Stage | Holder | What the research found (read 2026-10-23) |
|---|---|---|
| **Now** | Stripe, under the founder's personal tax status, which covers any tax. **Limited to $100,000 a year**; the running total is published, with no automatic cut-off (poll). Stripe replaced Buy Me a Coffee before launch (the maintainer, 2026-10-27): it carries OurHike's choice id through checkout, cancels by API, reports each renewal, and has no 5% platform fee. | Fees (read 2026-10-27): cards 2.9% + 30¢, Billing 0.7% of recurring volume, +1.5% on international cards and +1% more with a currency conversion (stripe.com/pricing, stripe.com/billing/pricing; older pages still say 0.8%). Not tax-deductible for the giver: "Gifts to individuals are not deductible" (IRS Topic 506). |
| **Next** | Open Source Collective as fiscal host — chosen over a 501(c)(3) sponsor and over going straight to a nonprofit (poll). | A 501(c)(6), so still not deductible; a "fixed 10% host fee" plus processor fees. **It will not pay "donations to unrelated causes or organizations" or "gifts or grant-style payments"**, so it cannot pass money to clubs (docs.oscollective.org). Open Collective Foundation, the 501(c)(3) host, ended fiscal sponsorship on 2024-09-30. |
| **Later** | OurHike's own nonprofit. | Where money can reach clubs. Not researched further. |

**Not decided here, and worth a tax professional before the page goes live:** whether this is a hobby or a business (Schedule C) for the founder. The IRS says to report income whether or not a Form 1099-K arrives. Publication 17 (2025) says "Hobby expenses… can no longer be deducted", so under hobby treatment tax would be owed on money spent entirely on OurHike. The 1099-K threshold is back to over $20,000 and over 200 transactions (IRS IR-2025-107); that release does not name the tax years.

## 3. The ask

- **On a hiker's 5th distinct day of use in a calendar year**, the app asks them to choose **$0, $12, $60 or $120 a year** — $1, $5 and $10 a month. The maintainer set these on 2026-10-27, replacing the $1, $10 and $100 of the 2026-10-23 poll.
  - A day is EVENTING.md §2's "active": a foreground session with at least one interaction.
  - The count is local and never sent: [`client/src/lib/activeDays.ts`](../client/src/lib/activeDays.ts).
  - 5 is the maintainer's number, not a measured one.
- **The choice is required, and $0 is a choice** (frame B, over a locked "safety mode" and over a dismissible reminder). Nothing is locked by not paying, and no feature reads a support state.
- **Yearly**, over monthly and over a per-hiker choice of schedule.
  - On a yearly charge, $0.73 of $12 goes to fees, $2.46 of $60 and $4.62 of $120 (Stripe's rates in §2; the arithmetic is mine). The flat 30¢ is paid once a year rather than twelve times.
- **No "not tax-deductible" line** on any page a hiker sees — the app's confirm sheet, the setup email, the /support/ site page, or Stripe's checkout (the maintainer, 2026-10-27). It is still true (§2); the hiker-facing copy just does not say it.
- **Picking $0 brings one more screen, once a year**: a nudge toward $12 or $60 in a hiker-trash voice.
  - Three of its lines spoke of "a dollar" or "a buck" when the lowest tier was $1 a year; they now say "a dollar a month" and "a buck a month", which $12 a year is.
  - Its headline rotates once a year per phone through five lines the maintainer kept from eight. The rotation is `NUDGES` in [`client/src/lib/support.ts`](../client/src/lib/support.ts).
  - Two button labels are the maintainer's own: "If you're forcing me…" and "Less money, less problems".
  - "Keep it at $0" is an underlined link under the paid buttons, always on screen and readable. That was chosen over a full button and over a second confirm, which would read as a dark pattern.
  - **No line puts a number on what a hiker costs to serve.** #393 measured a hiker who never signs in at about $0 a year, so any such line would be false.
- **The ask waits while the phone has no signal** (poll, 2026-10-24, over also waiting on a running hike and over asking regardless). The sheet covers the map until answered. No signal mostly means on trail. A paid choice cannot complete offline anyway.
- **It is decided once per launch, as the app comes up** ([`client/src/screens/SupportGate.tsx`](../client/src/screens/SupportGate.tsx)). The third #1885 review found it re-deciding whenever the day count, the signal or the account answer changed — so on day five it opened at the hiker's first tap, under their finger, and a signal returning mid-hike opened it over the map. Now it decides on the count this launch reaches, the first time the account answer is in and nothing holds the screen, and not at all after `ASK_WINDOW_MS` (fifteen seconds, `@unvalidated`). A launch that does not ask leaves it to the next. A signed-in hiker whose account could not be read is not asked: they may already pay.
- **The ask is dormant in any build without a backend** ("backend first", over a device-trusting interim). A paid choice is therefore verified from its first day live.
  - That waits on **#600 — Nothing owns standing up the production backend, and the image has never run against a real Docker daemon**.
  - What #600 still needs is the maintainer's to do: create the Render service, set its secrets, and set `API_BASE_URL`.

## 4. Verification, and what is kept

- **A $0 choice stays on the phone** and needs no account.
- **A paid choice is verified through a signed-in account.** The email is always the one on the account's token, never one typed into a form.
- **How a payment meets its choice: by id, never by email** ([`backend/app/core/support.py`](../backend/app/core/support.py)). The first #1885 review found a stranger's cancellation typed with a hiker's address could stop the hiker's choice; the third found the email fallback that survived it still let a stranger's payment land on the hiker's record, block the hiker's own choice, and be cancelled by the hiker's Stop. So there is no email matching at all:
  - by the provider's own id for the payment, wherever it has been seen;
  - otherwise by OurHike's own choice id, which the tier's Stripe Payment Link carries as `client_reference_id` and Stripe hands back on `checkout.session.completed` — onto that choice only while it is still `pending` and unpaid;
  - **a payment for a choice that no longer wants one** — already paid (two tabs), stopped (Stop pressed before the webhook landed), or emptied by an account deletion (a setup email paid afterwards) — gets a row of its own, is asked to stop at once, and the founder is emailed that it may need refunding;
  - **a payment that names no choice** (a link opened outside the app, or edited) is kept unattached, so the total is honest, and the founder is emailed; nobody can stop it from the app, and the founder cancels it if the payer writes in.
- **Only OurHike's own links are believed.** Every event must carry the `ourhike_tier_cents` metadata the Payment Links set, on the session, the subscription or the invoice's subscription snapshot. Anything else on the Stripe account can neither enter the total nor be cancelled with OurHike's key. A checkout counts only once `payment_status` is `paid`; a bank debit that settles later arrives as `checkout.session.async_payment_succeeded`.
- **A failing renewal** (Stripe's `past_due` or `unpaid`, while it retries the card) is `payment_failed`: still running, still blocking a second choice, and Stop cancels it at once rather than at the period's end, so no retry can charge after "nothing more will be charged".
- **Order and repeats.** Each row keeps the time of the newest event it took and drops anything older, and `stopped` is final for a provider id. A retried "updated" that arrives after the cancellation cannot bring the payment back.
- **Every event is kept** in `support_events` with what was done about it. The provider's module keeps a short named list of fields, never the payer's name, address, card or email. An event whose handling raised is stored as `failed` and still answered 200, because a provider eventually disables an endpoint that keeps failing and then nothing is recorded at all — **except** when the database itself is unreachable, which answers 503 so Stripe retries (for up to three days), since nothing could be recorded.
- **A webhook is believed only with Stripe's signature** (`Stripe-Signature`: HMAC-SHA256 of `<timestamp>.<body>` under the endpoint's secret), and only inside Stripe's five-minute replay window. `STRIPE_MODE` (`live` or `test`) says which mode's events are believed; a key or a Payment Link from the other mode switches support off rather than taking payments it would never record, which is how UA runs on Stripe's test mode safely.
- **Collected at the start** ("grab the right info from the get-go", poll) — model: [`backend/app/models/support.py`](../backend/app/models/support.py):
  - the email; the wording version shown (`terms_version`), the path (`delivery`) and when, which is the consent record for the stated term that a provider move means **one** email;
  - an **opt-in** yearly accounting email, off unless ticked, with when it was ticked;
  - the amount chosen beside the amount the provider reports, the currency, the cadence, the start and the renewal date (`period_end`);
  - the provider's ids: the subscription, the customer, and the tier's Payment Link or price.
  - **@unvalidated:** whether a Stripe customer id lets a later move skip the re-confirm. Stripe's own import guide copies customers but "Subscription data isn't copied".
- **The published total** (`GET /support/total`) is **read from charges**: the sum of every `invoice.paid` Stripe reports in the year, one `support_charges` row per invoice, which a unique key on the invoice id keeps from being counted twice — whether Stripe resends the event or reports one invoice as two events, and however many deliveries arrive at once. A charge counts even when it arrives before the checkout it belongs to, which Stripe does not promise to order, and is joined to the choice when the checkout lands. It counts US dollars only (another currency is left out rather than converted), and is computed at most once an hour per server. **A refund is not subtracted yet** — no refund event is handled — so a refunded charge keeps the total high.

## 5. No payment inside the app

- **The website app** (ourhike.org/app, today's product) sends a paid choice on to the tier's Stripe Payment Link. Its button reads "Continue to payment" (the maintainer's choice, 2026-10-27): Stripe's checkout shows OurHike's name, not Stripe's.
- **The iOS and Android apps** show the same four choices, still required (the maintainer, verbatim: "No Pyament in apps - but every hiker should be forced to choose an amount").
  - A paid answer is "Email me how to set it up". The payment link travels only by email — a Payment Link never expires, so the email can sit unread — and no screen in a store app names a payment provider.
  - Apple's guidelines (rev. 2026-10-16): 3.1.1(a) bars "buttons, external links, or other calls to action" to non-in-app purchase outside the US. 3.1.3 allows "communications outside of the app".
  - Google Play's Payments policy bars leading users "to a payment method other than Google Play's billing system". Google delisted WireGuard in 2019 over a donate link.
  - Neither store app is published yet (ROADMAP Phase 3).

## 6. Stop

- **More → Your support → Stop: on that page, one tap and one confirm, no reason asked.** We cancel it for the hiker, rather than sending them through a payment provider's account pages (frame A, poll 2026-10-23; Buy Me a Coffee's own cancel was about eight steps).
- **A choice nobody paid for** (`pending`, nothing confirmed) has nothing to cancel, so Stop clears it at once and the hiker can choose again. The first version marked it `stop_requested` and then refused every new choice.
- **A payment still charging** becomes `stop_requested`, **committed before anybody is asked**, and then the backend asks Stripe to stop it renewing (`cancel_at_period_end`), keeping the year already paid for — or to cancel it at once when its renewal is failing. The answer is recorded with an update that touches only the Stop's own columns, so a confirmation webhook landing during the call is never written over. The key it uses is a restricted one with Subscriptions: Write only.
  - When Stripe cannot be reached (no key, or Stripe refuses), the founder is emailed at `SUPPORT_NOTIFY_ADDRESS` to cancel by hand instead. That email lists every other record under the same address that is not stopped, so a person can see a stranger's payment beside the hiker's and pick the right one.
  - A request that does not go stays queued (`stop_notified_at` empty) and is asked again by the next Stop press, the hiker's next look at the page, and every webhook delivery — at most every `RETRY_EVERY` (fifteen minutes, `@unvalidated`) and five at a time, least recently tried first, so a provider outage is not hammered.
  - Stripe's `customer.subscription.updated` then marks it `cancel_scheduled` (no more charges, ends at the period's end), and **the hiker is emailed that it is done** — once, whichever order Stripe's events arrive in. `customer.subscription.deleted` at the end marks it `stopped`.
  - **A cancellation undone at Stripe** ("Don't cancel" in the dashboard) clears the Stop's bookkeeping, so the next Stop reaches Stripe again.
- **A receipt when a payment begins**: the amount, that it renews yearly on that date, and how to stop — what auto-renewal law expects, and the email that keeps a charge a year later from being a surprise.
  - The screen says exactly that, rather than claiming a cancellation that has not happened.
- **What the page offers is the server's answer.** `GET /support/me` carries `supporting`, `can_stop` and `can_choose`, so the app keeps no copy of the state machine. The states are `pending`, `active`, `payment_failed`, `paused`, `cancel_scheduled` (no more charges, ends at `period_end`), `stop_requested` and `stopped`.
- **Deleting an account** empties a choice nobody paid for — the address, the account, the accounting opt-in and the unsubscribe token go — but keeps it, `stopped`, under its id, so a setup email or open checkout tab paid afterwards is recognised and stopped rather than charging a deleted account forever. It asks for the same stop on anything still charging, because the deleted account can no longer reach the button. A paid record stays as the money record. See [`account_deletion.py`](../backend/app/core/account_deletion.py).
- **Every hiker-facing support email carries a real one-click unsubscribe** (`/support/mail/stop/{token}`, RFC 8058) once `API_PUBLIC_URL` is set. The store-app setup link goes at most once a day per address and amount, so a hiker who changes tier gets the link for the tier they chose.

## 7. Switching it on, and moving provider

| Where | Setting | What it does when empty |
|---|---|---|
| Backend host | `SUPPORT_PROVIDER` — where new choices go; default `stripe` | — (an unknown name answers 503 "not switched on") |
| Backend host | `STRIPE_PAYMENT_LINKS` — one Payment Link per tier, `1200=https://buy.stripe.com/…,6000=…,12000=…` | a choice answers 503 "not switched on" |
| Backend host | `STRIPE_MODE` — `live` (default) or `test`; which mode's events are believed | a key or link from the other mode switches support off, with a warning in the log |
| Backend host | `STRIPE_WEBHOOK_SECRET` — the endpoint's signing secret (`whsec_…`) | every webhook delivery is refused (503) |
| Backend host | `STRIPE_SECRET_KEY` — a **restricted** key, Subscriptions: Write only | Stop emails the founder to cancel by hand instead |
| Backend host | `SUPPORT_NOTIFY_ADDRESS` — where Stop requests go when Stripe cannot be reached | with no key either, the request waits in the retry queue |
| Backend host | `API_PUBLIC_URL` — this API's own https address | support emails' unsubscribe link points at the app's Your support page, which stops payments but not mail |
| Backend host | `MAIL_ENABLED` and SES | no support email sends |
| Stripe | one product with three **yearly** prices at $12, $60 and $120, a Payment Link for each, and a webhook endpoint at `<API>/support/webhooks/stripe` sending `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `customer.subscription.updated`, `customer.subscription.paused`, `customer.subscription.resumed`, `customer.subscription.deleted` and `invoice.paid` | — |
| GitHub variables | `API_BASE_URL` | the app's ask stays dormant, and the site's total reads "Not available" |

**Stripe's own pages carry OurHike's words, and they live here** because Stripe's dashboard is not a place anyone reviews. Each Payment Link is made with these settings, in test mode on 2026-10-27 (remade the same day with the corrected Stop line below) and the same again in live mode when that day comes:

- **Product** "Support OurHike"; three yearly USD prices, lookup keys `ourhike_support_1200_year`, `ourhike_support_6000_year`, `ourhike_support_12000_year`.
- **Under the Subscribe button** (`custom_text.submit`): "A yearly resupply for the map: charged today, then again on this date each year. Stop anytime in the OurHike app under More → Your support → Stop. No reason needed." (The maintainer chose this over two other wordings by poll, 2026-10-27, and asked for the tax line to go. It said "Two taps, no reason needed" until the third #1885 review counted four taps and possibly a sign-in.)
- **After paying** (`after_completion.hosted_confirmation`): "Resupply complete. Hike on back to OurHike; your choice shows under More → Your support in a minute or so."
- **Subscription description**: "Support OurHike, $12 a year" (and $60, $120), with `ourhike_tier_cents` in the link's and the subscription's metadata.
- **Set every field when the link is created.** Updating a link's text through the API cleared its subscription description, which the update call cannot set back (seen 2026-10-27, reported to Stripe), so wording changes mean a new link, the old one deactivated, and `STRIPE_PAYMENT_LINKS` updated.

**The provider seam.** Everything provider-shaped lives in [`backend/app/core/support_providers/`](../backend/app/core/support_providers/): a provider owns its checkout link, how its webhook is verified, how its events become OurHike's six kinds (`started`, `updated`, `failing`, `paused`, `ended`, `charged`, each charge with the provider's own id for it), whether it is `ready` to take choices, and how a cancel is requested (an API call, or an email to a person). The state machine, matching, ordering, the event log and the total do not change per provider, and the app's copy names none: it says "payment page", and only the website's Your support shows `provider_label` from the server. The seam was proved before launch: Buy Me a Coffee was replaced by Stripe (2026-10-27) as one module swapped. Adding Open Source Collective is a module beside `stripe.py` and one line in the registry.

**Moving a supporter.** Change `SUPPORT_PROVIDER`; every registered provider keeps receiving its own webhooks. A supporter still paying through the old one may choose again (their old payment no longer blocks a choice), the new choice records which one it replaces, and when the new payment starts the old one is asked to stop exactly as the hiker's own Stop would.

## 8. Open, and who settles it

- **The tax treatment** in §2 — a tax professional, for the founder.
- **What a paused subscription means for a yearly supporter.** It is recorded as `paused` and still counts as supporting (the hiker made a choice); nothing OurHike offers pauses one, so it would come from the Stripe dashboard.
- **Refunds.** No refund event is handled, so a refunded charge stays in the published total until one is.
- **`PENDING_GRACE_DAYS` = 30** — how long an uncompleted paid choice silences the ask. `@unvalidated`; real completion times would settle it.
