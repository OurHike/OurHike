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
| **Now** | Buy Me a Coffee, under the founder's personal tax status, which covers any tax. **Limited to $100,000 a year**; the running total is published, with no automatic cut-off (poll). | Fees: 5% platform, Stripe 2.9% + 30¢, 0.5% on subscription payments, 0.5% on payouts, +1% on international cards (Buy Me a Coffee's help article "How to calculate charges on your payment"). Not tax-deductible for the giver: "Gifts to individuals are not deductible" (IRS Topic 506). |
| **Next** | Open Source Collective as fiscal host — chosen over a 501(c)(3) sponsor and over going straight to a nonprofit (poll). | A 501(c)(6), so still not deductible; a "fixed 10% host fee" plus processor fees. **It will not pay "donations to unrelated causes or organizations" or "gifts or grant-style payments"**, so it cannot pass money to clubs (docs.oscollective.org). Open Collective Foundation, the 501(c)(3) host, ended fiscal sponsorship on 2024-09-30. |
| **Later** | OurHike's own nonprofit. | Where money can reach clubs. Not researched further. |

**Not decided here, and worth a tax professional before the page goes live:** whether this is a hobby or a business (Schedule C) for the founder. Buy Me a Coffee says income there "is subject to income tax", and the IRS says to report income whether or not a Form 1099-K arrives. Publication 17 (2025) says "Hobby expenses… can no longer be deducted", so under hobby treatment tax would be owed on money spent entirely on OurHike. The 1099-K threshold is back to over $20,000 and over 200 transactions (IRS IR-2025-107); that release does not name the tax years.

## 3. The ask

- **On a hiker's 5th distinct day of use in a calendar year**, the app asks them to choose **$0, $1, $10 or $100 a year**.
  - A day is EVENTING.md §2's "active": a foreground session with at least one interaction.
  - The count is local and never sent: [`client/src/lib/activeDays.ts`](../client/src/lib/activeDays.ts).
  - 5 is the maintainer's number, not a measured one.
- **The choice is required, and $0 is a choice** (frame B, over a locked "safety mode" and over a dismissible reminder). Nothing is locked by not paying, and no feature reads a support state.
- **Yearly**, over monthly and over a per-hiker choice of schedule.
  - On a yearly charge, $0.39 of $1 goes to fees, $1.19 of $10 and $9.20 of $100 (the rates in §2; the arithmetic is mine).
  - **$1 stays** knowing that.
- **Picking $0 brings one more screen, once a year**: a nudge toward $1 or $10 in a hiker-trash voice.
  - Its headline rotates once a year per phone through five lines the maintainer kept from eight. The rotation is `NUDGES` in [`client/src/lib/support.ts`](../client/src/lib/support.ts).
  - Two button labels are the maintainer's own: "If you're forcing me…" and "Less money, less problems".
  - "Keep it at $0" is an underlined link under the paid buttons, always on screen and readable. That was chosen over a full button and over a second confirm, which would read as a dark pattern.
  - **No line puts a number on what a hiker costs to serve.** #393 measured a hiker who never signs in at about $0 a year, so any such line would be false.
- **The ask waits while the phone has no signal** (poll, 2026-10-24, over also waiting on a running hike and over asking regardless). The sheet covers the map until answered. No signal mostly means on trail. A paid choice cannot complete offline anyway.
- **The ask is dormant in any build without a backend** ("backend first", over a device-trusting interim). A paid choice is therefore verified from its first day live.
  - That waits on **#600 — Nothing owns standing up the production backend, and the image has never run against a real Docker daemon**.
  - What #600 still needs is the maintainer's to do: create the Render service, set its secrets, and set `API_BASE_URL`.

## 4. Verification, and what is kept

- **A $0 choice stays on the phone** and needs no account.
- **A paid choice is verified through a signed-in account.** The email is always the one on the account's token, never one typed into a form.
- **How a payment meets its choice** ([`backend/app/core/support.py`](../backend/app/core/support.py)). Tightened after the #1885 adversarial review found the first version matched any event by email, so a stranger's cancellation typed with a hiker's address could stop the hiker's choice:
  - by the provider's own id for the payment, wherever it has been seen;
  - otherwise, only for a **started** event, by email onto a `pending` choice for the **same amount**, on the **same provider**, chosen no later than the payment began (plus `EMAIL_MATCH_SKEW`, ten minutes, `@unvalidated`);
  - a payment that matches nothing is kept unattached, so the total is honest, and attached to the account whose **verified** email it carries the next time that account opens Your support. That is also how a supporter who paid on the provider's page gets a Stop button.
- **Order and repeats.** Each row keeps the time of the newest event it took and drops anything older, and `stopped` is final for a provider id. A retried "updated" that arrives after the cancellation cannot bring the payment back.
- **Every event is kept** in `support_events` with what was done about it. A provider's module drops the supporter's display name, their note, a cancellation reason and the email before anything is stored. An event whose handling raised is stored as `failed` and still answered 200, because Buy Me a Coffee switches a webhook off after ten failures in a row and then nothing is recorded at all.
- **Collected at the start** ("grab the right info from the get-go", poll) — model: [`backend/app/models/support.py`](../backend/app/models/support.py):
  - the email; the wording version shown (`terms_version`), the path (`delivery`) and when, which is the consent record for the stated term that a provider move means **one** email;
  - an **opt-in** yearly accounting email, off unless ticked, with when it was ticked;
  - the amount chosen beside the amount the provider reports, the currency, the cadence, the start and the renewal date (`period_end`);
  - the provider's ids: the payment, the person, the level, and the card processor's subscription behind it (Stripe's, for Buy Me a Coffee).
  - **@unvalidated:** whether Stripe's id lets a move skip the re-confirm. Buy Me a Coffee says it uses "Stripe Standard Connect", which would put the subscriptions in the creator's own Stripe account, and nobody has checked. Stripe's own import guide copies customers but "Subscription data isn't copied".
- **The published total** (`GET /support/total`) is **reasoned from start dates, not read from payouts.** Nothing Buy Me a Coffee sends reports a renewal charge, so a refund, a failed card or a paused membership's skipped charge would make the total high. It counts US dollars only (another currency is left out rather than converted), and is computed at most once an hour per server.

## 5. No payment inside the app

- **The website app** (ourhike.org/app, today's product) sends a paid choice on to Buy Me a Coffee's checkout.
- **The iOS and Android apps** show the same four choices, still required (the maintainer, verbatim: "No Pyament in apps - but every hiker should be forced to choose an amount").
  - A paid answer is "Email me how to set it up". The payment link travels only by email, and no screen in a store app names Buy Me a Coffee.
  - Apple's guidelines (rev. 2026-10-16): 3.1.1(a) bars "buttons, external links, or other calls to action" to non-in-app purchase outside the US. 3.1.3 allows "communications outside of the app".
  - Google Play's Payments policy bars leading users "to a payment method other than Google Play's billing system". Google delisted WireGuard in 2019 over a donate link.
  - Neither store app is published yet (ROADMAP Phase 3).

## 6. Stop

- **More → Your support → Stop: one tap and one confirm, no reason asked.** We cancel it for the hiker. Chosen over sending them through Buy Me a Coffee's own cancel, which is about eight steps after logging in there (its help article).
- **A choice nobody paid for** (`pending`, nothing confirmed) has nothing to cancel, so Stop clears it at once and the hiker can choose again. The first version marked it `stop_requested` and then refused every new choice.
- **A payment still charging** becomes `stop_requested`, and whoever cancels it is asked. Buy Me a Coffee has no cancel API, so that is an email to `SUPPORT_NOTIFY_ADDRESS` to cancel it by hand the same day.
  - The email lists every other record under the same address that is not stopped. A provider names a supporter only by an email anybody can type, and the founder cancelling by hand is the one point a person can see both and pick the right one.
  - A request that does not go stays queued (`stop_notified_at` empty) and is asked again by the next Stop press, the hiker's next look at the page, and every webhook delivery.
  - The provider's cancellation event then marks it `stopped`, and **the hiker is emailed that it is done**.
  - The screen says exactly that, rather than claiming a cancellation that has not happened.
- **What the page offers is the server's answer.** `GET /support/me` carries `supporting`, `can_stop` and `can_choose`, so the app keeps no copy of the state machine. The states are `pending`, `active`, `paused`, `cancel_scheduled` (no more charges, ends at `period_end`), `stop_requested` and `stopped`.
- **Deleting an account** deletes a choice nobody paid for, and asks for the same stop on anything still charging, because the deleted account can no longer reach the button. A paid record stays as the money record. See [`account_deletion.py`](../backend/app/core/account_deletion.py).
- **Every hiker-facing support email carries a real one-click unsubscribe** (`/support/mail/stop/{token}`, RFC 8058) once `API_PUBLIC_URL` is set. The store-app setup link goes at most once a day per address.

## 7. Switching it on, and moving provider

| Where | Setting | What it does when empty |
|---|---|---|
| Backend host | `SUPPORT_PROVIDER` — where new choices go; default `buymeacoffee` | — (an unknown name answers 503 "not switched on") |
| Backend host | `BUYMEACOFFEE_CHECKOUT_URL` — the page's membership URL, https only | the website path answers 503 "not switched on" |
| Backend host | `BUYMEACOFFEE_WEBHOOK_SECRET` — shown on the webhook's page in Buy Me a Coffee | every webhook delivery is refused (503) |
| Backend host | `BUYMEACOFFEE_LEVEL_IDS` — the membership levels that are OurHike support, comma-separated | every level on the page is believed |
| Backend host | `SUPPORT_NOTIFY_ADDRESS` — where Stop requests go | Stop is recorded and the hiker told, and the request waits in the retry queue |
| Backend host | `API_PUBLIC_URL` — this API's own https address | support emails' unsubscribe link points at the app's Your support page, which stops payments but not mail |
| Backend host | `MAIL_ENABLED` and SES | no support email sends |
| Buy Me a Coffee | three **yearly** membership levels at $1, $10 and $100, and a webhook pointed at `<API>/support/webhooks/buymeacoffee` | — |
| GitHub variables | `API_BASE_URL` | the app's ask stays dormant, and the site's total reads "Not available" |

**The provider seam.** Everything provider-shaped lives in [`backend/app/core/support_providers/`](../backend/app/core/support_providers/): a provider owns its checkout link, how its webhook is verified, how its events become OurHike's four kinds (`started`, `updated`, `paused`, `ended`), and how a cancel is requested (an API call, or an email to a person). The state machine, matching, ordering, the event log and the total do not change per provider, and the app's copy says "payment page" rather than a name. Two exceptions, both on the website only: Your support shows `provider_label` from the server, and the pay button keeps "Continue to Buy Me a Coffee" by the maintainer's choice (2026-10-27), so moving provider means changing that one string in `SupportAsk.tsx`. The store apps name no provider anywhere. Adding Open Source Collective is a module beside `buymeacoffee.py` and one line in the registry.

**Moving a supporter.** Change `SUPPORT_PROVIDER`; every registered provider keeps receiving its own webhooks. A supporter still paying through the old one may choose again (their old payment no longer blocks a choice), the new choice records which one it replaces, and when the new payment starts the old one is asked to stop exactly as the hiker's own Stop would.

## 8. Open, and who settles it

- **The tax treatment** in §2 — a tax professional, for the founder.
- **What `membership.paused` means for a yearly supporter.** It is recorded as `paused`, still counts as supporting (the hiker made a choice), and is counted in the total as if it charged; the first real event settles which of those is wrong.
- **Whether a renewal arrives as `membership.updated`.** If it does, the total could read real charges rather than infer them from start dates.
- **`PENDING_GRACE_DAYS` = 30** — how long an uncompleted paid choice silences the ask. `@unvalidated`; real completion times would settle it.
