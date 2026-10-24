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
- **A paid choice is verified through a signed-in account.**
  - Buy Me a Coffee's signed `membership.*` webhooks are matched to the email on the account's token, never to one typed into a form.
  - The mechanism is [`backend/app/core/support.py`](../backend/app/core/support.py).
  - Signature recipe: HMAC-SHA256 of the raw body, hex in `x-signature-sha256`, from Buy Me a Coffee's webhook OpenAPI spec (read 2026-10-23). Test events carry `live_mode: false` and are ignored.
- **Collected at the start** ("grab the right info from the get-go", poll):
  - the email, plus the stated term that a provider move means **one** email asking the supporter to move;
  - an **opt-in** yearly accounting email, off unless ticked.
  - The record also keeps the amount in cents and its currency, the cadence, every date, Buy Me a Coffee's membership id, and Stripe's subscription id (`psp_id` in the payload). Model: [`backend/app/models/support.py`](../backend/app/models/support.py).
  - **@unvalidated:** whether Stripe's id lets a move skip the re-confirm. Buy Me a Coffee says it uses "Stripe Standard Connect", which would put the subscriptions in the creator's own Stripe account, and nobody has checked.
- **The published total** (`GET /support/total`) is **reasoned from start dates, not read from payouts.** Nothing Buy Me a Coffee sends reports a renewal charge, so a refund or a failed card would make the total high.

## 5. No payment inside the app

- **The website app** (ourhike.org/app, today's product) sends a paid choice on to Buy Me a Coffee's checkout.
- **The iOS and Android apps** show the same four choices, still required (the maintainer, verbatim: "No Pyament in apps - but every hiker should be forced to choose an amount").
  - A paid answer is "Email me how to set it up". The payment link travels only by email, and no screen in a store app names Buy Me a Coffee.
  - Apple's guidelines (rev. 2026-10-16): 3.1.1(a) bars "buttons, external links, or other calls to action" to non-in-app purchase outside the US. 3.1.3 allows "communications outside of the app".
  - Google Play's Payments policy bars leading users "to a payment method other than Google Play's billing system". Google delisted WireGuard in 2019 over a donate link.
  - Neither store app is published yet (ROADMAP Phase 3).

## 6. Stop

- **More → Your support → Stop: one tap and one confirm, no reason asked.** We cancel it for the hiker. Chosen over sending them through Buy Me a Coffee's own cancel, which is about eight steps after logging in there (its help article).
- **No cancel API was found**, so the backend marks the choice `stop_requested` and emails `SUPPORT_NOTIFY_ADDRESS` to cancel it by hand the same day.
  - The `membership.cancelled` webhook then marks it `stopped`.
  - The screen says exactly that, rather than claiming a cancellation that has not happened.
- **Deleting an account requests the same stop**, because the deleted account can no longer reach the button. The record stays as the money record. See [`account_deletion.py`](../backend/app/core/account_deletion.py).

## 7. Switching it on

| Where | Setting | What it does when empty |
|---|---|---|
| Backend host | `BUYMEACOFFEE_CHECKOUT_URL` — the page's membership URL | the website path answers 503 "not switched on" |
| Backend host | `BUYMEACOFFEE_WEBHOOK_SECRET` — shown on the webhook's page in Buy Me a Coffee | every webhook delivery is refused (503) |
| Backend host | `SUPPORT_NOTIFY_ADDRESS` — where Stop requests go | Stop is recorded and the hiker told, but nobody is emailed |
| Backend host | `MAIL_ENABLED` and SES | the store apps' setup email and the Stop notice do not send |
| Buy Me a Coffee | three **yearly** membership levels at $1, $10 and $100, and a webhook pointed at `<API>/support/webhooks/buymeacoffee` | — |
| GitHub variables | `API_BASE_URL` | the app's ask stays dormant, and the site's total reads "Not available" |

## 8. Open, and who settles it

- **The tax treatment** in §2 — a tax professional, for the founder.
- **What `membership.paused` means for a yearly supporter.** It is left unchanged and logged; the first real event settles it.
- **Whether a renewal arrives as `membership.updated`.** If it does, the total could read real charges rather than infer them from start dates.
- **`PENDING_GRACE_DAYS` = 30** — how long an uncompleted paid choice silences the ask. `@unvalidated`; real completion times would settle it.
