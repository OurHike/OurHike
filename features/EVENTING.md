# OurHike — Eventing & Measurement (v2, built for six events 2026-10-27)

Companion to [FEATURE_GATING.md](FEATURE_GATING.md), [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md) and [OurHikeValues.md](../OurHikeValues.md).

**Read §0 first.** It is what is built. §1 to §12 are the design this document opened with on 2026-08-09, kept in place, with their section numbers unchanged because a dozen files cite them by number. Each section now says whether it still holds. Two of its rules were reversed on purpose, and §0 says which ones, by whom, and what the reversal costs.

---

## 0. What was decided on 2026-10-27, and what it changed

**#1902 — Count six usage events with a sealed account id and GPS fix, keep them six months, close each month into a table, and report them per club** is the build. The maintainer asked for it on 2026-10-26 and settled it in three polls on 2026-10-27, then the four questions the adversarial review left in a fourth poll the same morning, each answered against a drawn page or real frames. The issue records every option, the ones taken and the ones declined. In short:

| Decision | Chosen | Declined |
|---|---|---|
| How an event holds the user and their position | **Encrypted and masked.** The account id and the exact GPS fix are sealed. Reports read a keyed hash of the account, a 0.1° square and a club. | A one-way pseudonym plus a coarse area only, with no exact fix anywhere. Or this document's original design: no identifier and no geography (#870). |
| Which position | **Where the phone is**: the GPS fix the map already holds | Where the map is looking |
| How the sealing works | **Write-only**: the backend holds public keys and cannot open what it wrote. Each month's key is **derived from one secret plus the month's name**: "not perfect, but a little better". | Independent monthly keys shredded at six months. Sending a fix only near a trail, rounded to ~110 m. Sending a position only on rows from hikers who opted in. |
| Consent | **Split.** Counts are on by default, with an off switch. Linking the account is asked once after sign-in. | Everything on by default. Everything off until asked. |
| Clubs | **The club whose trail the event is about.** A plan is split across clubs by its miles in each. | Only where the hiker stands. Only from hikers who opted in. |
| Small numbers | **"<25" everywhere, masked when the report is built.** "Don't mess with the data." | Exact numbers in the maintainer's copy. A floor of 10. |
| The dashboard | **A Python script writing one branded HTML file**, filterable by dates and club | A screen in the app. SQL views only. |
| Room for six months of raw rows (poll 4) | **Keep six months, and move to a paid database plan before daily phones near 300**, raising the storage ceiling with it | Raw rows only until each month closes. Pausing collection whenever the ceiling is full. |
| An identifier for phones that never link (poll 4) | **None**: no id and no install month on their rows | An install month on one row a month. A random id new each month. A permanent random id. |
| The wording the review corrected (poll 4) | **Approved as corrected** | Shorter wording with the same facts. Changing the behaviour to keep the old promises. |
| A public issue for the nightly checks (poll 4) | **Kept**: check names, slices and days, never a figure | The private report only. A public issue naming no check. |

**What this reverses: §1's rules 1 and 2** — "No identifier is sent" and "No geography, ever" — for the six events below. The reason those rules existed has not changed. **#252 — Remove `reporter_id` from the public report serialisation** removed exactly this pair, a stable account id next to a position and a date, from a public API. This build stores the pair, behind a seal the server cannot open. The exact pair is now as safe as the maintainer's secret, and no safer. **A coarse copy of it is not behind that secret**: for a hiker who said yes, `user_key` sits beside the 0.1° square and the date in the clear, and the backend holds both the key's secret and every account id, so it can recompute any linked hiker's key and read their dated squares for six months (the review's finding, 2026-10-27; "left open", below). §6's "what is never collected" list and the [Privacy Policy](../site/public/Privacy/index.html) now say so plainly.

**What is still true from below:**
- §1 rules 3 and 4: no free text, no time finer than a date, and measurement never competes with a queued report.
- §2's heartbeat, which is how hikers who said no are still counted exactly.
- §5's experiments, unbuilt.
- §6's floor of 25, now applied when a report is built.
- §7's warning about what engagement numbers mean.

### The six events

`client/src/lib/usageEvents.ts` holds the registry on the phone, and `app/models/analytics.py` `UsageEvent` holds it on the server. `POST /usage-events` refuses any other name.

| Event | Sent when | What it may carry besides the common fields |
|---|---|---|
| `app_installed` | the first launch of an install that had not finished first run, as the app can see it. A store install is counted by the stores, and a reinstall or cleared storage counts again here. An install that predates measurement is not counted, and neither is its first event | — |
| `user_login` | a sign-in **this app started** finishes (`client/src/lib/signInMarker.ts`). A session restored at launch is not a sign-in, and neither is supabase-js's `SIGNED_IN`, which also fires when a tab regains focus | club at the fix |
| `hike_plan_made` | a long hike is started, a section or trip is laid out (new ones only), a day hike or suggested route is newly saved, or the planned A.T. hike is saved. That last one counts every save, edits included, because a planned hike has no identity to tell an edit from a new plan | `miles`; clubs split by miles where the plan is on the A.T. |
| `hike_plan_completed` | a long hike is finished, or a day hike's walk is logged, including a saved route walked again - but not a second log for a day already logged, which changes nothing | `miles`; clubs split by miles where the plan is on the A.T. |
| `map_screen_viewed` | the map comes into view, once per arrival | club at the map's centre |
| `session` | a visit is over: the app out of sight for more than 30 minutes, or found unfinished at a launch more than 30 minutes after it was last seen. A relaunch within the 30 minutes - a phone that killed the app, an OAuth redirect reloading the page - continues the same visit | `pageviews` (screens shown), `session_length` in four buckets, the first fix the map held during the visit and its club. The row belongs to whoever the visit began with: signed in or not, linked or not |

**Common fields on every row:**
- the phone-minted id
- the phone's calendar date
- the platform and the app version
- the heartbeat flags (`week_first`, `month_first`, `ever_first`), and `club_firsts`, the same "first time this month" answer per club (§2)
- three more answers the phone works out about itself, added on 2026-10-27 when the maintainer asked how signed-in and signed-out hikers are told apart (below): `kind_month_first` (its first event of this kind this month), `month_returning` (on its first row of the month: it was counted last month too) and `signed_in` (an account is signed in on it - never which)
- the phone's GPS fix, but only one the map already holds that is under 10 minutes old and within 100 m. Measurement never turns location on.

**Linked rows** need three things: the hiker said yes on the phone, the phone sent a valid token with the batch, and **the account's synced preferences hold the yes**. The server reads `measurement_linked` from the account's last `PUT /preferences/me` (`_synced_consent` in `backend/app/routers/analytics.py`), so a yes links nothing until it has synced. Linked rows also get a `user_key` (HMAC-SHA256 of the account id under `ANALYTICS_USER_KEY_SECRET`), and the account id goes into the seal beside the fix. A queued row remembers which account recorded it (`client/src/lib/accountTag.ts`) and goes linked only while that same account is signed in with its yes standing, so one hiker's rows never leave with another's token; a sign-out or a no sends what is waiting unlinked rather than dropping it, and takes the account's tag off it - the visit still in progress included, which kept its tag until 2026-10-27 (`unlinkWaitingRows` in `client/src/lib/usageQueue.ts`).

**The server holds an account to its synced answers.** A batch carrying a token whose account synced "off" stores nothing: it is counted as `declined` and answered 202 with every row refused, so the phone drops it. An unlinked batch carries no token, by design, so the server cannot check it; what stops those is the phone's own switch, which a signed-in phone takes from the account at every launch ("A sync carries a consent answer only from the device that gave it", below).

**Taking back a yes unlinks what it linked.** When a sync turns `measurement_linked` off, or turns measurement off while linked, `forget_link` (`backend/app/core/analytics_accounts.py`) deletes the account's User-table rows, takes `user_key` off its events and drops each event's sealed blob, in the same transaction as the preference. The blob goes whole because it holds the account id beside the exact fix, and the server cannot take the account out alone. The row is marked `seal = 'unlinked'` and keeps its count and its 0.1° square, like a row from a hiker who said no. Kept, the blob would leave the account readable to `open` for up to seven months after the no, and out of reach of a later account deletion, which finds rows by their key. Found on 2026-10-27 while the review's fixes were being checked against the code, with a test that fails without it (`backend/tests/test_analytics_account.py`).

**The hiker's two answers are kept the way they were given.** Found by the adversarial review of #1903 on 2026-10-27, each with a test that fails without it:

- **A sync carries a consent answer only from the device that gave it** (`client/src/lib/preferences.ts` `consentTouched`). Preferences sync as one blob, and before this a first sign-in adopted the account's untouched "on" over an "off" just set on the phone, and a phone pushing a units change sent its stale "on" over another phone's "off". An answer given here now survives a pull and is pushed; an answer not given here is never pushed, and the account's comes back with the push. A signed-in launch sends nothing until the account's preferences have been reconciled once.
- **A yes belongs to the account that gave it.** Sign-out and account deletion forget `measurement_linked`, so the next hiker to sign in on a shared phone is asked rather than linked by the last one's yes.
- **The stored answers are the ones used.** A launch applies the stored record even after an early tap on the mode switch, holds any preference changed before the record answered and applies it on top, and starts measuring only once the record was actually read.
- **"Off" holds in every open tab**: it is a flag in the store the tabs share, a row recorded while it is set is refused, and a send in progress stops at it. A flush reads the store again before each batch, and a token goes with a batch only when the token's own `email` claim is the account the rows were recorded under.

**The server refuses rows one at a time.** A row that breaks the registry, or is dated before retention or more than a day ahead, is refused alone; before 2026-10-27 one such row cost every row in its batch, since the phone drops a refused batch. The registry is strict about shape: an app version is three numbers with an optional pre-release (`VERSION_PATTERN` in `backend/app/schemas/analytics.py`, so `1.5.0+7` and `1.5` are refused), and a club id is at most 16 characters. Every row's outcome is counted per day and app version in `analytics_intake` (stored, duplicate, invalid, too old, future), which is the only trace a refused row leaves.

**Three outcomes turn a whole batch away unread**, counted under no version:
- `over_budget`: the day has already stored `analytics_daily_row_budget` = 50,000 rows, or more rows are held than `analytics_storage_ceiling_mb` = 250 MB allows at 382 bytes a row, about 686,000 (`backend/app/config.py`; both `@unvalidated`, "Operating it" step 6). Answered 503 with `Retry-After: 3600`, which the phone treats as "keep and send later" (`sendUsageBatch` in `client/src/lib/usageQueue.ts`). **The ceiling counts rows held, not the table's size on disk** (`backend/app/core/analytics_storage.py`): a Postgres table's file does not shrink when rows are deleted - measured 2026-10-27, a 30 MB table with its oldest month deleted and vacuumed stayed 30 MB - so a ceiling on file size, once met, would have refused every batch for good, months after the rollup deleted the rows that filled it. Rows held are summed from `analytics_intake`'s stored counts, which the rollup deletes on the same date line as the rows.
- `paused`: the nightly rollup has not run for `analytics_rollup_stale_days` = 3 days (Retention, below). Answered the same way.
- `declined`: the token's account synced "off" (above). Answered 202 with every row refused, so the phone drops them.

**None of measurement is parsed before the first frame.** App renders `client/src/lib/DeferredMeasureUsage.tsx`, which imports the hook behind `import()`; what App must still build eagerly - the props, the plan calls, the link question - was paid for by deferring eight tap-opened surfaces that take no focus (`client/src/screens/deferred.ts` has the measurements and why a surface that takes focus stays eager), and the preferences reconciliation loads on the first sign-in rather than at launch (`client/src/lib/usePreferencesSync.ts`). Moments in the first second, before the chunk arrives, are missed: a screen change, or a plan made that fast. The install is captured eagerly, so a fast Skip on first run still counts.

**What the phone does to keep its own counts right**, the same review: a club share is never 0 (the remainder of rounding goes to the largest club and a sliver past a boundary is no club's - 4.3% of 220,000 synthetic plans had been refused for it); the queue, when full, drops rows that count nothing before a phone's first row of a week or month; switching sharing off and on keeps which periods were counted, so the phone is not new again; the install and the mark that it was counted are one write; and a plan call can never throw into the hiker's own save.

### Who is who: signed out, signed in, linked

The maintainer's question of 2026-10-27, answered as built. **There is no device id and no anonymous id**: a phone is never told apart from another phone by anything it sends. What a report can say comes from three states and from what each phone answers about itself.

| The phone is | What its rows carry about who | What a report can count |
|---|---|---|
| **Signed out** | nothing - and `signed_in: false` | phones (active, new, returning, back again, and per thing done), by the phones' own answers |
| **Signed in, not linked** (said no, or not asked yet) | nothing about the account - `signed_in: true` | the same, and what share of phones are signed in |
| **Signed in and linked** (said yes) | `user_key`, a keyed hash of the account; the account id sealed | all of the above, plus hikers: who came back, planned and finished, across months and phones, from the User table |

So the **phone** is the unit for everyone, and the **hiker** is the unit only for those who said yes - two numbers the report never adds together. A hiker with two phones is two phones and one hiker. A phone's rows before a hiker linked are not joined to the rows after; nothing could join them without an identifier. **Growth accounting for every phone** - new, returning from last month, back after a gap, lost since last month - comes from `ever_first` and `month_returning` on each phone's first row of the month, and adds up exactly to the month's active phones (checked nightly, below).

What this does not give, said rather than discovered: **retention by install cohort for phones that never linked** (month-over-month return is there; "of the phones installed in March, how many are here in July" is not), and **a journey across sessions for an unlinked phone**. Both need either an identifier or an install-month field on rows, and both cost something §1 was written to avoid: for a small population, an install month plus platform and version makes most phones unique, and their rows linkable across months with the 0.1° square beside them. **The maintainer chose to make neither trade** (poll 4, 2026-10-27): no identifier and no install month on an unlinked phone's rows.

### Keeping the numbers honest over time

Eventing data goes wrong quietly - a field renamed, a call dropped in a refactor, a flag that fires twice - and the count just comes in low or high. Each of these fails a test first:

- **The heartbeat, over histories a real phone records** (`client/src/lib/usageHeartbeat.test.ts`): 400 seeded histories with sessions recorded after later rows and clocks stepping both ways; every week, month, club-month and kind-month counted exactly once. It found the bug it was written for: the heartbeat remembered only the last week and month, so a visit across Sunday midnight or a month end counted the phone twice in both (on synthetic histories with clock steps off, 1,458 of 2,243 phone-months; the real rate was never measured). It keeps sets of counted periods now.
- **The golden batch** (`client/src/lib/usageBatch.golden.test.ts` and `backend/tests/test_usage_golden_batch.py`): one row of every event with every field, built by the phone's code into a checked-in file the server must store field for field. A rename on either side fails one of them.
- **What a metric means is fingerprinted** (`DEFINITION_FINGERPRINTS`, `backend/tests/test_analytics_definitions.py`): changing the metric SQL, `_MONTH_ROWS`, `CLOSE_AFTER_DAYS` or the router's `_UPSERT_USER` (which decides who is new) without recording it under a `DEFINITION_VERSION` fails. `compute_month`'s Python is deliberately not covered, and `definition_fingerprint`'s comment says why.
- **Eight months of phones through the real route and the real nightly rollup** (`backend/tests/test_analytics_simulation.py`): installs, churn, linked accounts, and offline trips long enough to upload after a month closed; every closed month's phones, new, returning and back-again equal the simulation's own truth as of the close, closed months never move, late rows are counted exactly, the oldest month's raw rows go and its figures stay. It found that "late rows" were counted from `received_on > closed_on`, which missed rows arriving later on the close day itself; the count is now rows held less rows frozen.
- **The wiring, in a real browser** (`client/e2e/usageCensus.spec.ts`): one install for a fresh first run, one visit closed on relaunch, no sign-in for a restored session, one map view per arrival, nothing kept once sharing is off, and the batch as actually sent - unlinked, no token.
- **The sums that must hold**, nightly on real data (next section).

### Data quality: what is checked every night

`backend/app/core/analytics_quality.py`, after the rollup, from the same workflow:

- **Each metric each day** - installs, sign-ins, plans made and completed, map views, visits, phones first this week (`VOLUME_METRICS`) - against the median of the same weekday over up to eight weeks, **compared lag for lag**: a day is judged against earlier days as they stood after the same number of whole days of uploads, so a fresh day short of its offline phones does not read low every night. Visits and phones first this week are also judged **for each platform** (`PLATFORM_METRICS`), so a whole platform going silent shows while the other two carry the total.
- **Counts are judged only for falls** (`low`, `zero`). A rise is the season more often than a fault: the review of 2026-10-27 measured `high` on 51% of nights of a synthetic series climbing 6% a week, and on a flat synthetic series of 20 a day `judge` still called a rise on 7 of 154 nights (measured the same day). **Each event per visit is judged both ways**, because instrumentation that starts counting twice shows there while the season does not.
- **An anomaly needs two things**: 4 deviations out *and* 50% away from expected - so it neither fires on noise at 20 a day nor on a 3% wobble at 10,000. **A fall to nothing is judged on its own**: zero where at least 7 were expected (`ZERO_MIN_EXPECTED`, a Poisson chance under 0.1%) and at most a quarter of the same weekday's history was zero (`ZERO_HISTORY_SHARE`). It was "never zero" until the review saw that one earlier outage would switch the rule off for that weekday for eight weeks. Too little history says `learning`, too few events `quiet`. Every threshold is `@unvalidated`; what settles them is a quarter of real data and the maintainer's judgement of which findings were worth reading.
- **Each release against the others**, the shape of a release that stopped recording one event (a row with no readable version is reported as `version:(none)`); **refused and resent rows** from `analytics_intake`; **batches turned away** as `over_budget` or `paused` (`rows_over_budget`, `rows_paused`); **rows held past four-fifths of the storage ceiling** (`storage_near_ceiling`, `STORAGE_WARN_SHARE`), the notice to move to a paid plan while batches still go in; **a night the rollup step failed** (`rollup_failed`, passed in by the workflow); **rows thrown away for want of a key**; **a month left provisional past its close**; **closed months still collecting rows** (`CLOSE_AFTER_DAYS` too short); and **the sums every month must satisfy** - platforms add up to the whole, new + returning + back again = active, session lengths add up to sessions, no club above the whole app. A month's sums are judged while it is open and for `MONTH_JUDGED_DAYS` = 14 days after it closes. After that its last finding stays in `analytics_anomalies` as history and is not made again, so the tracking issue can close.
- Findings go into `analytics_anomalies` and resolve themselves when a later night no longer makes them. **Production keeps one tracking issue** while any is open (`.github/scripts/tracking-issue.js`), the maintainer's choice in poll 4 over the private report alone or an issue that names no check. A statistical finding (`low`, `high`, `zero`) reaches it only on its second night (`public_findings`), so one odd day emails nobody; a `broken` or `warn` finding goes in at once, and a check that starts failing while the issue is already open is announced in a comment, so a second fault is not silent. This repository is public, so the issue and the job's log name checks, slices and days and **never a figure** (`backend/tests/test_analytics_quality_script.py`); the figures are in the table and the report. The database engine is built with `hide_parameters=True` (`backend/app/db/session.py`), and both nightly commands print only `describe_failure` on an error, never a traceback, so a failed statement cannot print the values it was bound to.
- **Checked against a staged incident** on the demo seed, and re-run on 2026-10-27 after the review's changes: release 1.5.0 refusing plan rows from 2026-10-12 was found by the per-release check and the intake check, and a two-day sign-in outage by the zero rule, with nothing else firing across 56 days of the volume and ratio checks, and no broken sums. The tracking issue would have carried the refused rows that night and the rest from the next.

### Encrypted and masked: what the server can and cannot read

- **Sealed** (`analytics_events.sealed`): the account id and the exact fix. The backend seals to the month's public key from `analytics_seal_keys` and holds no private key at all (`app/core/analytics_seal.py`). If no key is published for the month, both are thrown away and the row says `no_key`. Nothing is ever kept in the clear to be sealed later.
- **Masked, readable by reports**: `user_key`, the fix's 0.1° square (about 11 × 8 km at 41° N, by its south-west corner), and the clubs.
- **Never written**: the IP address (no column could hold it, and the backend's own access log drops its line for `/usage-events`: `DropUnloggedPaths` in `backend/app/core/logs.py`), the time of day, free text, the account id in the clear. The hosting platform in front of the backend may still log the address of every request it forwards ("What this build does not do", below).
- **Opening a sealed row** is `backend/scripts/analytics_keys.py open`, run by the maintainer on their own machine with the secret from their password manager. It writes an `analytics_openings` row naming who, which month, what was asked for and why, commits that row *before* it decrypts anything, and writes the rows to a CSV file, never to the terminal. The secret is read only at a hidden prompt, never from a variable or an argument, since either ends up in shell history. The CSV must be outside the repository and must not exist yet, and it is created readable by the maintainer's account alone (mode 0600).
- **The month in the key** means an opening for October derives October's key and no other month's. It is **not shredding**: the secret derives any month's key again. A sealed position stops being readable only when its row is deleted. A database backup taken before that delete stays readable with the secret until the backup itself expires.

### Retention and the monthly close

`app/core/analytics_rollup.py`, run nightly by `.github/workflows/analytics-rollup.yml`:

- **Kept six months**, counted in whole months. The current month and the six before it are held, so a row lives between six and seven months.
- **Each month is recomputed** into `analytics_monthly` while open, and **closed 14 days after it ends**.
- **Closed months are frozen.** Late arrivals after the close are counted in `events_after_close` and change nothing else.
- **A month's raw rows are deleted only after it has closed.** The run fails rather than delete numbers nobody froze.
- **Nothing is collected while the delete is not running.** `POST /usage-events` reads the rollup's heartbeat, the newest `analytics_months.computed_at`. Once it is older than `analytics_rollup_stale_days` = 3 days, every batch is turned away as `paused` and stays on the phone. Three days is reasoned from the nightly schedule: two missed nights and a late third. The rollup recomputes the current month every night, rows or none, so a quiet night still counts as a run, and the current month always has a row in `analytics_months`, as zeros on a night with no rows. A new database collects nothing until the rollup has run against it once.
- **One run at a time.** `run()` first takes a transaction-level advisory lock, so a manual dispatch beside the schedule waits and then finds the month already closed. Not `REPEATABLE READ`: that takes its snapshot at the first statement, which would be the lock itself, before the wait, so the second run would act on the months as they stood before the first closed them. `--today` may only be a past date.

The month-end snapshot problems the strategy page listed, and where each answer lives, are in that module's docstring. The ones that shape the data:
- **Distinct counts do not add up across months.** Each month freezes its own, and `analytics_users.active_months` answers uniques across months after the raw rows are gone.
- **"As of month end" stocks** are milestone *dates* on the User table rather than a snapshot, so any "as of" is a `WHERE` clause.
- **The month is the phone's calendar**, not UTC's.

**`CLOSE_AFTER_DAYS = 14` is @unvalidated.** It is §2's "most recent fortnight is provisional", reasoned and not measured. `events_after_close` is the measurement that will settle it.

### The User table

`analytics_users` holds one row per hiker who said yes:
- first and last seen, with their platforms
- `new_month`, the month the hiker counts as new: set by their first linked batch and never moved, so a late row from a second phone cannot take them out of a closed month's new hikers. A known edge, stated rather than fixed: a hiker whose first linked batch is dated wholly inside a month already closed is new in a month frozen without them - missed, never counted twice
- the dates of their first sign-in, first plan and first completion
- lifetime counts and miles
- `active_months`
- `updated_on`, the day of the last batch that changed it: a date, not a time, because the time of an upload is when a hiker found signal

It is updated at ingest, so a resend never counts twice. It is kept until the account is deleted or the hiker takes back their yes (above). `app/core/account_deletion.py` deletes it with the linked events, and the export hands the hiker every plain column of their events and this row as `your_usage_summaries`, a list with one entry per secret the account was keyed under (normally one). **It has no location column, and must not get one**: a per-hiker home area kept for the life of an account would be #252's pair without even the six-month limit.

**Rows are found under every secret.** Deletion, export and unlinking recompute the account's `user_key` under `ANALYTICS_USER_KEY_SECRET` and each of `ANALYTICS_USER_KEY_PREVIOUS_SECRETS` (`account_user_keys`). With no secret set while linked rows exist, `DELETE /profiles/me` refuses with 503 and changes nothing, rather than report usage gone that it could not find (`LinkedUsageUnreachable`), and the export says it could not look.

### Clubs

The phone works out the club, from data it already holds:
- `clubAtMile` in `client/src/lib/clubSections.ts` for an A.T. mile
- the publishing organization for other trails

It sends a closed-alphabet id of at most 16 characters (`ClubId` in `backend/app/schemas/analytics.py`), never a name. `_unrecorded` stands for the 38.5 A.T. miles whose club ATC's own centreline does not name; it is distinct from "not on a trail". A plan's share in each club is its miles there over its total miles. The schema accepts shares adding to within 0.02 of one, and the server divides each row's shares by their own sum before storing them (`normalised_shares`), so the stored shares of a plan add up to exactly one plan. Plans and miles add up across clubs. Hikers do not, and should not: one hiker can plan in two clubs.

### The report

`backend/scripts/usage_report.py` writes one self-contained HTML file in OurHike's style:
- the logo lockup, a pine header and paper body
- From, To and Club filters
- active devices by month, a by-club table, plans and completions, platforms and session length
- retention by first month, from the User table
- every phone by what it did (viewed the map, planned, completed), beside the same funnel for hikers who said yes; where each month's phones came from (new, returning, back again, lost); the share signed in
- a data-health panel: what was linked, what was thrown away for want of a key, what arrived after its month closed, and how far ahead keys are published
- a data-quality panel: each count's days as a **share** of what was expected, never a count, and only where 25 or more were expected; a fixed band from half to one and a half times expected, inside which a day is never called an anomaly; a hollow dot for an anomalous day too small to show as a share; and every finding of the last sixty days. No band edges per day are published: the review recovered the exact count on 50 of 56 days from `high / expected = 1 + 4/√E`

**Every figure describing fewer than 25 people is absent from the file**, not hidden by its script (`app/core/analytics_report.py`):
- **A cell of 1 to 24 phones is masked whole.** A cell of 0 is shown as its zeros, so an app with no web users does not hide Android with it; any other figure inside a 0-phone cell is masked, since it describes phones nobody counted.
- **A count inside a shown cell** is masked below 25, and so is one whose complement in the cell is below 25 - of 900 phones, "880 viewed the map" says 20 did not. New, returning and back-again phones add up to the cell's active phones, so one of them masked masks all three.
- **Events follow their people** (`FOLLOWERS`): installs are masked with new phones, plans and their miles with the phones that planned, completions and their miles with the phones that completed, sign-ins and map views with theirs, and linked events with the hikers active.
- **No hidden figure can be had by subtraction.** One hidden club takes the next-smallest with it. Platforms add up exactly, so hidden platform cells stay hidden together until they hold 25 phones between them, and a figure masked in one platform cell is masked in the next-smallest too, preferring one whose own figure is not zero. A 0-phone club or platform is never the one picked, since hiding a zero hides nothing.
- **"Lost since last month" is worked out on the server** (`devices_lost`: last month's active phones less this month's returning ones), and masked when either input is or the result is 1 to 24. Masking it alone would hide nothing while both inputs were shown, so this month's returning phones, and with them new and back again, are masked too whenever that difference is 1 to 24. The review asked only for the first; the second is what makes the first hide anything.
- **Cohorts and the User-table line** take the complement rule: a retained count is masked when it, or the cohort less it, is 1 to 24, and so are the hikers who ever planned or finished.

The script refuses to write inside the repository. It reads the plain columns of `analytics_events` for the quality panel, never `sealed`, which the rollup role's grants already allow.

### Operating it

1. **Make the secret, once:** `python backend/scripts/analytics_keys.py new-secret`. It goes into the maintainer's password manager and nowhere else.
2. **Publish the public keys ahead of time:** `DATABASE_URL=<owner URL> python backend/scripts/analytics_keys.py publish --from 2026-11 --months 24`, once per database (UA and production). It asks for the secret at a hidden prompt; paste it from the password manager. The report warns when fewer than three months are left.
3. **Set `ANALYTICS_USER_KEY_SECRET`** on the backend's host, a long random string different from the secret above. Unset, nothing is ever linked to an account, and that is a valid deployment - but unsetting it once rows were linked stops account deletion until it is restored (The User table, above). **To rotate it**, set the new value and move the old one into `ANALYTICS_USER_KEY_PREVIOUS_SECRETS` (comma-separated, so a secret holding a comma cannot be listed). Never drop an old secret while a row stored under it exists: raw rows go within seven months, but a User-table row lasts until its account is deleted, so in practice an old secret stays listed for good. The cost: a hiker who linked before a rotation has two User-table rows after it, and is counted as two hikers in the User-table line and in cohorts.
4. **Create the rollup's role and set its secrets.** Run the SQL below, then set `PRODUCTION_ANALYTICS_DATABASE_URL` and `UA_ANALYTICS_DATABASE_URL` (`.github/expected-settings.yml`). The username is tenant-qualified, exactly as the conditions reader's is.
5. **Run the rollup once** (dispatch `analytics-rollup.yml`) before expecting any rows. Until its first run, `POST /usage-events` answers `paused`, and phones keep what they hold.
6. **Size the storage ceiling to the plan.** `analytics_storage_ceiling_mb` (250 by default) and `analytics_daily_row_budget` (50,000) are `@unvalidated` and live in `backend/app/config.py`. One measurement to set them by: 100,000 synthetic rows of all six events, half of them sealed, inserted into an empty `analytics_events` on Postgres 16 took 380 to 382 bytes a row by `pg_total_relation_size`, both indexes included (two runs, 2026-10-27), so 250 MB holds about 686,000 rows at the higher figure, the one the ceiling uses. That is about three weeks at §8's estimate of 33k rows a day, against six to seven months of retention, so at that scale the ceiling, not the budget, is what binds. **The maintainer's choice (poll 4, 2026-10-27): keep six months, and move to a paid database plan before daily phones near 300** - roughly where six months of rows outgrow 250 MB at 6 to 11 rows a phone a day - raising the ceiling to the new plan's room. The nightly checks raise `storage_near_ceiling` at four-fifths of the ceiling, about 137,000 rows before it: six to eleven weeks of notice at 300 phones a day.

### The rollup's role

It can read every usage column **except** `sealed`, delete raw rows, and write the monthly tables. So the one scheduled job holding a production credential for usage data cannot read a position or an account even by mistake:

```sql
CREATE ROLE ourhike_analytics_rollup LOGIN PASSWORD '<generated>';
GRANT CONNECT ON DATABASE postgres TO ourhike_analytics_rollup;
GRANT USAGE ON SCHEMA public TO ourhike_analytics_rollup;
GRANT SELECT (id, local_date, received_on, event, platform, app_version, user_key,
              week_first, month_first, ever_first, club_firsts, kind_month_first,
              month_returning, signed_in, clubs, miles,
              pageviews, session_length, has_fix, area_lat, area_lon, seal)
  ON public.analytics_events TO ourhike_analytics_rollup;
GRANT DELETE ON public.analytics_events TO ourhike_analytics_rollup;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.analytics_months, public.analytics_monthly,
  public.analytics_anomalies TO ourhike_analytics_rollup;
GRANT SELECT, DELETE ON public.analytics_intake TO ourhike_analytics_rollup;
GRANT SELECT ON public.analytics_users, public.analytics_seal_keys TO ourhike_analytics_rollup;
-- RLS is on with no policies for every analytics table (migration 897b71ad5fff), so the
-- role needs one per table it touches:
CREATE POLICY rollup_events ON public.analytics_events FOR ALL TO ourhike_analytics_rollup USING (true);
CREATE POLICY rollup_months ON public.analytics_months FOR ALL TO ourhike_analytics_rollup USING (true);
CREATE POLICY rollup_monthly ON public.analytics_monthly FOR ALL TO ourhike_analytics_rollup USING (true);
CREATE POLICY rollup_users ON public.analytics_users FOR SELECT TO ourhike_analytics_rollup USING (true);
CREATE POLICY rollup_keys ON public.analytics_seal_keys FOR SELECT TO ourhike_analytics_rollup USING (true);
CREATE POLICY rollup_intake ON public.analytics_intake FOR ALL TO ourhike_analytics_rollup USING (true);
CREATE POLICY rollup_anomalies ON public.analytics_anomalies FOR ALL TO ourhike_analytics_rollup USING (true);
```

The same role can build the report. It cannot run `open`, by design; that needs the owner's URL.

### What this build does not do, said rather than discovered

- **No limit per sender on `POST /usage-events`.** What the route stores is bounded (the day's budget and the storage ceiling, above), but nothing tells one sender from another - no IP, no account - so a flood can skew a day's counts and use up its budget, holding real rows back to the next day. Fake events could not reach anybody's data.
- **The hosting platform may log addresses.** The backend drops its own access line for `/usage-events`, but the platform in front of it may record the address of every request it forwards, and nothing in this repository can turn that off. The Privacy Policy's "Standard technical information" paragraph says so.
- **Positions are collected from anywhere, including homes.** That is the trail-only package declined in poll 2. A home is the place that names a person fastest, which is why opening a sealed row is logged.
- **Positions are collected from hikers who said no to linking**, sealed and without an account. That is the yes-only package declined in poll 2. The question after sign-in says "either way" for this reason.
- **Clubs are shown by their ids** (`NYNJTC`, `GATC`). The report has no names table.
- **Only A.T. miles get a club.** A day hike or any plan on another trail is counted by its length with no club. Its club would be the organization that publishes that trail, which the app does not yet look up. A map view or session off the A.T. corridor (more than 3 miles from its centreline, `MAX_OFF_TRAIL_MILES`) has no club either.
- **Hikers already signed in when this ships are not asked** the link question until their next sign-in. The question is asked only after a sign-in the app started, so it never interrupts a launch. Until then they are counted unlinked, and can link from Safety & privacy.
- **The App Store and Play privacy declarations** have to list precise location and usage data before a store build ships this. That is store-console work outside this repository.
- **No identifier for an unlinked phone**, so no install-cohort retention and no cross-session journey for phones that never link (above, "Who is who"). The maintainer's choice, poll 4.
- **A refused row's reason is not stored**, only its kind (`invalid`, `too_old`, `future`) and the version that sent it. Finding which field broke means reproducing the release.
- **Nobody with a licence to say so has reviewed this design**, §9's caveat, which applies with more force now that it holds an identifier and a position.

Found by #1903's adversarial review and left open, each one the maintainer's to weigh:

- **The database knows which rows arrived together.** Each batch is one insert in one transaction, so its rows share Postgres's `xmin` - one phone's rows, up to 200 of them, across days - and a phone's unlinked batch and linked batch get consecutive transaction ids, which could tie anonymous rows to the `user_key` beside them. Reproduced on Postgres 16 by the review, and it survives `VACUUM FREEZE`. The fix is a staging table emptied into `analytics_events` nightly in one transaction ordered by `id`, which needs a `SECURITY DEFINER` function so the rollup's role can move a `sealed` column it may not read.
- **The phone holds a readable trail while offline**: queued rows keep full-precision positions with dates, up to 200 of them, until they are sent - against the rule `App.tsx` and `lib/walkedMiles.ts` keep for the walked-miles record (no coordinates, no timestamps, no ordering). Sealing on the phone with the month's public key, or dropping the fix from a row unsent after some hours, would close it; both change what the maintainer asked for.
- **A row's content can link a phone's rows to each other**: date, platform, version and the 0.1-degree square single out a phone where few hikers are, and a plan's club shares (four places) and miles (one) nearly encode its ends. Coarser shares and miles would cost little.
- **Nothing is said before the first rows are sent.** The install and the first visit leave as soon as the app is online; first run's location card mentions usage statistics, and "Skip" passes it.
- **No daily-active count**: there is no `day_first` answer, so DAU is not computable, and §2 promised it.
- **The sign-in that asks the link question is never itself linked** - it is recorded before the answer - so `analytics_users.logins` misses each hiker's first.
- **A linked hiker's coarse whereabouts are readable by the backend**, not only with the maintainer's secret. The backend holds `ANALYTICS_USER_KEY_SECRET` and every account id, so it can recompute any linked hiker's `user_key` - which is exactly how deletion, export and unlinking find rows - and read that hiker's dated 0.1° squares and clubs for six months. The rollup's credential in Actions reads `user_key`, square and date per row too. Closing it means a `user_key` the backend cannot recompute, and deletion and unlinking would then have to find rows another way.
- **The floor of 25 rests on counts phones assert.** The review sent 25 rows with no account, each carrying only `club_firsts: ["SMALLCLUB"]`, and took a 3-hiker club from fully masked to showing its plans (3) and miles (25.5). Anyone who receives the report and can send rows can unmask a club-month that way; the daily budget bounds how many rows a sender adds, not whether.
- **The sealing secret cannot be rotated.** `publish` refuses to overwrite a month, and step 2 publishes 24 months ahead, so after a leak new positions are sealed to the leaked keys until somebody deletes `analytics_seal_keys` rows by hand.
- **The opening record is not tamper-evident.** `analytics_openings` lives in the database the opener has owner rights on.
- **A month is computed in four statements, each with its own snapshot** (`compute_month` under READ COMMITTED). A plan row arriving between two of them, during the run that closes a month, would freeze that month's club plans above its total plans. Reasoned by the review and not reproduced; the window is milliseconds, once a month. A session-level lock taken before a `REPEATABLE READ` transaction would close it.
- **A `zero` in the public issue is a figure**: it says a count was nothing that day. It is the only one the issue carries.
- **The rollup's credential can delete the frozen history** (`analytics_monthly`, `analytics_months`), so a leaked repository secret could erase it. An Actions environment limited to `main` would keep the secret away from pull-request workflows, and a separate role for the delete would narrow it further.

Two docs, one subject, split on a line worth stating up front: **FEATURE_GATING.md owns the gate — what a hiker sees. This doc owns the measurement — what we learn from it.** That doc's §6 sketched a starting event taxonomy and then deferred its own fourth open question, "how to minimize the privacy footprint of the event taxonomy above while still preserving useful experiment signal … not assumed safe by default." This is that pass, and the answer changed the taxonomy rather than trimming it.

**What this has to deliver:** MAU, WAU and DAU. Evidence about which features work and which do not. Something A/B tests and feature gates can be measured against rather than a second parallel system beside them. Collected client-side, because the app is offline-first and a server-side scheme sees almost nothing. And none of it may cost a hiker their privacy.

---

## 1. The constraint that shaped everything else

Measurement wants an identifier. This app cannot safely have one.

That is not a general privacy preference, it is a specific finding this repository has already made and paid for. [#252](https://github.com/OurHike/OurHike/issues/252) removed `reporter_id` from the public report serialisation because a stable account UUID served next to a trail position and a time is a hiker's route down the corridor, recoverable with `curl` and no account — see [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md). The dangerous pair was *stable identifier* + *where and when*. An analytics scheme is exactly a machine for producing that pair, several times a day, for every hiker, forever.

So the design starts from the hard version of the question: **what can be measured with no identifier at all?** More than expected — enough that the identifier turns out to be unnecessary for the whole of §2 and §3, and avoidable for most of §5. Where one is genuinely required, §5 makes it a per-experiment decision with a scope and an expiry, not a standing fact about a hiker.

Four rules, and everything below is a consequence of them:

1. **No identifier is sent — not an account id, not a device id, not a session id, not a rotating pseudonym.** Deduplication happens on the device, which is the only party that already knows its own history and therefore the only one that learns nothing new by doing it.
   *Reversed for hikers who say yes, 2026-10-27 (§0, #1902): their rows carry a keyed hash of the account, and the account id sealed. Rows from everyone else still carry no identifier, and the deduplication described here is what counts them.*
2. **No geography, ever.** No coordinates, no mile, no segment id, no POI id, no region. This is the #252 half of the pair, and on a trail app it is the more dangerous half.
   *Reversed, 2026-10-27 (§0, #1902): every usage event carries the phone's fix, sealed, plus a readable 0.1° square and a club. The sentence about which half is more dangerous is still true, and is why the fix is sealed rather than stored.*
3. **No free text, and no timestamp finer than a date.** Date, not time; a bounded enum from a reviewed registry, never a string a hiker typed.
4. **Nothing measurement-related may compete with a hiker's queued report** — not for storage, not for bandwidth, not for the sync that gets a blowdown to a moderator. Measurement is the first thing dropped and the last thing sent.

## 2. DAU, WAU and MAU without an identifier

The reflex is that unique-user counts *require* a stable id: the server has to tell whether two visits a fortnight apart came from one phone or two. The reflex is wrong, and the reason is that the server is the wrong party to ask. **The device already knows. Let it answer, and send the answer instead of the evidence.**

Once a day at most, on a day it was used, the client emits one **heartbeat** carrying a date and three booleans:

```
active_day
  date          2026-08-09          the day being described, not the day it uploaded
  week_first    true | false        first active day this ISO week
  month_first   true | false        first active day this calendar month
  ever_first    true | false        first active day, full stop
```

That is the entire payload. The server counts:

| | |
|---|---|
| **DAU** for a day | heartbeats carrying that date |
| **WAU** for a week | heartbeats in that week with `week_first` |
| **MAU** for a month | heartbeats in that month with `month_first` |
| **New devices** | heartbeats with `ever_first` |
| **Stickiness** | DAU ÷ MAU, from the three above |

A device active four days in a week sends four heartbeats and exactly one of them says `week_first`, so the week's count is a count of devices without anybody ever having distinguished one device from another. The numbers are exact, not estimated — no HyperLogLog sketch, no sampling error, and nothing to re-identify because the heartbeats carry nothing that differs between two devices active on the same day.

**Four things this costs, stated rather than discovered later:**

- **Calendar windows, not rolling ones.** This yields MAU for August, not MAU for the trailing 28 days. ISO weeks are deliberate — they start Monday, so a Saturday–Sunday weekend hike lands inside one week rather than being counted twice. A Sunday-to-Monday trip still straddles. Rolling windows can be reconstructed by adding a bucketed gap-since-last-active to the heartbeat, at the cost of a weak chaining channel (a run of gaps sketches one device's history), so it is deliberately not in v1.
- **Late arrivals are the normal case, not the exception.** A hiker offline for nine days uploads nine heartbeats when they next get signal, each carrying its own date. Every dashboard therefore treats the most recent fortnight as provisional and says so on the chart. A design that assumed same-day delivery would show a cliff at the right-hand edge and somebody would eventually read it as a decline.
- **A batch is momentarily linkable at the ingest boundary.** Nine heartbeats arriving in one request obviously came from one device. The guarantee is that the joinable form is never *written*: the ingest path increments counters and discards the request grouping, which is a property a test can assert rather than a promise in a doc. It is a real narrowing of the claim and worth knowing — "unlinkable in the store", not "unlinkable on the wire".
- **A wrong device clock produces a wrong date.** Reject future dates, clamp anything absurd, accept the residue. It is an accuracy problem, not a privacy one.

**"Active" needs a definition, because an offline-first app can inflate this by accident.** A heartbeat means *a foreground session with at least one hiker interaction*. A background sync is not activity, a service-worker wake is not activity, and a phone that opened the app in a pocket is a problem for whoever writes the interaction check.

## 3. Which features are working

Counts alone answer "is this used", which is the easier and less useful question. Two families, and the second is the one that earns its keep.

**Counters — one row per feature per device per day, not one per tap.**

```
feature_day
  date, feature (from the registry), uses (bucket: 1 | 2 | 3-10 | 11-50 | 51+)
```

Bucketing the count is not tidiness: an unbucketed 383 is rare enough to be a fingerprint, and nothing is lost, because no decision anybody makes here turns on 383 versus 400.

**Outcomes — did the thing the feature exists for actually happen.**

```
task_outcome
  date, task (from the registry),
  outcome  completed | abandoned | failed,
  duration (bucket: <10s | 10-60s | 1-5m | >5m),
  offline  true | false
```

Summarised **on the device, at the end of the attempt**, and sent as one row. There is no session identifier because there is no need to stitch a session together server-side once the device has already answered the question the stitching was for.

The cost is real and cuts the other way from every hosted analytics product: **a question nobody thought to ask cannot be asked of old data.** No exploratory funnel over last quarter's stream, because there is no stream. Adding a question means adding it to the app and waiting weeks for it to answer. Two things make that trade acceptable here rather than merely tolerable — a stream that could answer arbitrary later questions is precisely a stream that could answer "where was this hiker in March", and this project already believes a feature should know what it is for before it ships, which §7 turns into the rule that makes it work.

**The registry is code, not convention.** `task` and `feature` are members of a TypeScript union in the client and a matching enum in the backend, and the ingest route rejects anything outside it. That is what stops rule 3 — no free text — from being a thing everyone remembers until the afternoon somebody interpolates a POI name into an event key.

**One error signal, deliberately narrow.** [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md)'s error-boundary decision says "Nothing is recorded… a deliberate no, revisitable if a real need appears." A screen that turns white for some hikers and nobody hears about it is that need. What v2 adds is a count — `screen_crashed{screen}` — and specifically **not** the message, the stack, or anything derived from them, since a stack trace is exactly the unbounded string rule 3 exists to keep out. A count says *the map screen died 40 times last week*; that is enough to go looking, and it is all this is allowed to say.

## 4. Do not instrument what the server already knows

Client-side collection is forced by the architecture, not preferred. Panning the map, reading a waypoint card, following a route in a valley with no signal — none of it reaches a server, so a server-side-only scheme is blind to nearly everything worth learning.

But some of it *does* reach the server, and those things must not be sent twice:

| Already a server-side record | Do not add an event for |
|---|---|
| A report, closure or thanks submitted | "report submitted" |
| A sync performed | "app synced" |
| A map package downloaded from R2 | "download completed" |
| An account created or signed in | "signed up" |

Counting these from the records that already exist is more accurate (it survives an opt-out and a dropped queue), cheaper, and smaller — and every event not sent is a payload not carrying anything. The rule: **the client instruments only what no server-side record can answer.**

*2026-10-27 (§0): `user_login` is sent by the client anyway. A sign-in is a record in Supabase Auth, not in this backend, and reading Auth's tables needs a service-role key `app/config.py` does not hold, the gap `app/core/account_deletion.py` already names. Until that changes, the client is the only party that can answer "how many sign-ins".

## 5. Experiments, and the identifier they turn out not to need

[FEATURE_GATING.md](FEATURE_GATING.md) already settles the mechanism: variants are evaluated locally from a cached manifest, synchronously, with a hardcoded fallback, so a hiker on a ridge is never waiting on a flag service. Nothing here changes that. What this section settles is how the result gets measured.

**A/B test on a binary outcome needs no per-user data at all.** Exposures per variant and successes per variant are two proportions, and a two-proportion test wants four integers, not four hundred thousand rows. Aggregate is not a degraded input to that test; it is a sufficient one. So an experiment adds one field to §3's shapes:

```
task_outcome + variant        (from the local evaluation; "control" when unenrolled)
exposure_day: date, experiment, variant     (deduped on the device, one per day)
```

For ratio metrics — uses per active device, say — aggregates alone lose the variance the test needs, and the fix is still not an identifier: the device sends its bucketed per-device count (§3 already does), and a histogram per variant carries the distribution. **Send histograms, not rows.**

**Where that genuinely does not stretch, the escape hatch is scoped and expires.** Some metric one day will need per-unit data — variance reduction against pre-period behaviour, most likely. The answer then is an **experiment-scoped random id**: generated at enrolment, used by that experiment only, never reused across experiments so two of them cannot be joined into a profile, and deleted with the experiment's data when it ends. Identity scoped to a single question and destroyed with it is a different object from an analytics id, and the difference has to be enforced by the schema rather than remembered. Taking the hatch is a per-experiment decision with a written reason, not a default.

**This partly unpicks FEATURE_GATING.md's tool choice, and the doc should say so rather than let somebody discover it during setup.** GrowthBook's warehouse-native analysis expects a row per user per metric; this shape has no such rows and will not grow them. Its *flagging* half — manifest, targeting rules, local evaluation, the per-chapter rules in that doc's §4 — is unaffected and still the recommendation. Its *analysis* half sits unused until either an experiment takes the hatch above or somebody decides the hatch should be the default. The arithmetic GrowthBook would have done is a two-proportion test with a Bayesian posterior, which is a short script in `pipeline/` against the same DuckDB the data platform already runs. Choosing that first is consistent with how this repository has chosen everything else in the data platform.

**At club scale, most A/B tests cannot answer the question they are asked.** For 80% power at α = 0.05 against a 20% baseline conversion:

| Effect to detect | Devices per arm |
|---|---|
| 20% → 30% (a big change) | ~260 |
| 20% → 22% | ~6,400 |
| 20% → 21% (a 5% relative lift) | ~25,600 |

A beta with NYNJTC members can find the first row and cannot find the third — not slowly, not at all. **So the default for a change that is probably an improvement is a staged rollout watched against guardrails, not an experiment**, and A/B is reserved for genuine disagreements about big effects. This also lands on the same practical footing FEATURE_GATING.md already noted from the other direction: GrowthBook's automated guardrails are Enterprise-only, so guardrail watching is a person reading a weekly summary either way.

**No experiment arm may withhold, delay, or de-emphasise safety information.** Closures and serious warnings are never the "off" arm of anything. Presentation can be tested — wording, placement, which of two equally prominent treatments reads faster — provided no arm shows a hiker *less* than control, or later than control. This is [OurHikeValues.md](../OurHikeValues.md) #4 stated as a schema constraint: a flag key marked `safety_surface` is refused an experiment, in the manifest, rather than trusted to a reviewer noticing.

## 6. What is deliberately never collected

Worth a list, because "we are careful" is not a specification and the absent things are the whole design:

Location of any kind, at any resolution · mile or segment or POI id · report contents, drafts, or anything a hiker typed · search terms · account id, email, or trail name · device id, install id, advertising id · IP address (see §8) · cookies · user-agent strings · session replay or screen recording · anything from a third-party SDK, because there are none · timestamps finer than a date · unbounded numbers where a bucket does.

*2026-10-27 (§0): location and the account id moved off this list for usage events. Both are collected, sealed so the server cannot read them, and masked in everything a report reads. Everything else here still stands, IP address and time of day included.*

**And one on the output side: no published or stored cell below k = 25 devices.** A count of three is a description of three people, especially when it is broken down by club. Suppression is at the query layer, applied to every breakdown, so that the interesting-looking slice nobody thought about is covered too. Whether 25 is right for a beta whose chapters may not reach it is §11's problem, not a reason to omit the floor.

## 7. What the numbers are allowed to mean

This app is unusual in what it wants: [HIKER_SAFETY.md](HIKER_SAFETY.md) and [FEATURES.md](../FEATURES.md) both commit to hikers using it *less often*, finding what they need faster, with "no reason to manufacture engagement." **Engagement metrics therefore point the wrong way here, and DAU is not a goal.** A rising session length may mean the map got confusing. Time-on-elevation-profile going up may mean the ribbon got harder to read.

Two rules keep the numbers honest:

- **Every engagement metric is read next to a task-success metric, never alone.** Uses of the water-source filter mean nothing; uses paired with `completed` versus `abandoned` mean something. §3's two families exist as a pair for this reason.
- **A feature ships with its success measure named in its own design doc, or ships unmeasured on purpose.** One or two sentences: what this is for, what it would look like if it were working, what would make us withdraw it. Written before it ships, because a measure chosen afterwards is chosen knowing the answer. §3's registry is where those measures become code, and "unmeasured on purpose" is a perfectly good answer for a feature whose value was never in doubt.

The failure this is guarding against is not a wrong number. It is the ordinary one where a metric goes up, everybody is pleased, and nobody notices it went up because the app got worse in a way that made people look at it more.

## 8. Where it lands

*Superseded by §0, 2026-10-27. What was built: `POST /usage-events` writes `analytics_events`, kept six months rather than 35 days. A nightly rollup closes months into `analytics_monthly` rather than days into `event_daily`. The "weekly summary read by a person" became a generated HTML report. The diagram and the volume arithmetic below are the first design's, kept for the reasoning.*

```
[Client]  in-memory during the day; one summarised batch appended to the existing outbox
   |      capped (~32 KB / 200 rows); oldest measurement rows dropped first;
   |      never displaces a queued report; sent after reports, fire-and-forget,
   |      credentials: 'omit'; failure is silent and never retried aggressively
   v
[POST /events]  FastAPI, first-party, no cookies, no auth.
   |            Validates every field against the registry; rejects anything else.
   |            Does not log the IP for this route and does not persist request grouping.
   v
[Postgres]  received rows, 35-day retention (late arrivals, corrections), then dropped
   |        by a scheduled job that is tested rather than remembered
   v
[Nightly rollup] -> daily aggregates kept indefinitely (small) + Parquet in R2
   v
[DuckDB]  the weekly summary, and the experiment arithmetic from §5 — the same
          stack pipeline/ already runs, queried by a script, not a dashboard product
```

**Volume, so nobody has to guess at cost:** 3,000 daily devices × one heartbeat plus ~10 summary rows ≈ 33k rows/day, ~1.2M rows in the 35-day window, and daily aggregates measured in kilobytes per day. This is a small table in the Postgres that already exists, and the rollups fit in a repository file if it ever came to that.

**No dashboard product in v1.** A generated weekly summary — the counts from §2, the task outcomes from §3, the opt-out rate from §9, the crash counts, each with its k-floor applied — read by a person. Boring, cheap, and it fails visibly. A dashboard nobody opens is the same collection with a worse excuse.

**The privacy claim is only as good as the ingest route**, so it needs its own tests rather than its own paragraph: an event carrying an unregistered key is rejected; an event carrying coordinates is rejected; the IP is absent from what is written; the retention job actually deletes; a k-floor breakdown suppresses. That is a small suite, and it is the load-bearing part of this whole document.

## 9. Consent, disclosure, and the off switch

*Answered 2026-10-27 (§0), in the direction this section's own rule pointed: **identifier ⇒ consent.** Counts are on by default with an off switch ("Share usage statistics", Settings → Safety & privacy). Linking the account is asked once, after sign-in ("Link your usage to your account?"), and changeable on the same screen. A position is sent on default-on rows too, because the maintainer declined to make it consent-only. The question after sign-in says so ("either way"), and so does the Privacy Policy.*

The site's Privacy Policy already made the promise this has to keep: "We don't currently run any analytics… We're likely to add some limited, aggregated analytics in the future… we'll update this page when it happens rather than after the fact." **The page is updated in the same change that ships the first event, not after** — and the design above was shaped so the update can be short and true: no identifiers, no location, no free text, dates not times, nothing shared with anyone, nothing sold, no third parties.

- **Default on for everything in §2 and §3**, which carry no identifier and no location. Off in one tap in Settings, and off means collection stops, not that it is anonymised harder.
- **Any future addition that carries an identifier of any kind is opt-in instead.** Including §5's escape hatch. The rule is mechanical — *identifier ⇒ consent* — because that is the one that survives being applied by whoever is here in two years.
- **Publish the opt-out rate next to the numbers.** An opt-out is a hole in the denominator and the hole is not random: the hikers who switch it off are not an average slice of the hikers. DAU that quietly undercounts by a drifting amount is worse than DAU that says so.
- **What the shape is aiming at, without claiming it has arrived:** the audience-measurement exemptions European regulators grant to first-party, non-tracking, aggregate measurement (CNIL's is the clearest) describe roughly this design. Data with no identifier is largely outside GDPR's subject matter, but ePrivacy governs *storing anything on a device* regardless — and §2's dedupe needs a local counter. Nobody with a licence to say so has reviewed this. Somebody should before it ships to a general audience, and the design is deliberately the version most likely to survive that review.

## 10. Data model

*Superseded by what was built (§0, 2026-10-27): `analytics_events`, `analytics_months`, `analytics_monthly`, `analytics_users`, `analytics_seal_keys` and `analytics_openings` (backend/app/models/analytics.py). On the phone, the heartbeat state below lives in `client/src/lib/usageEvents.ts`, and the switches are `measurement_enabled` and `measurement_linked` on `UserPreferences`. The sketch below is the first design's.*

```
# Client, IndexedDB — alongside the existing outbox, never ahead of it
MeasurementState
  last_active_date        date | null
  last_week_key           ISO year-week | null      (drives week_first)
  last_month_key          year-month | null         (drives month_first)
  has_ever_been_active    bool                      (drives ever_first)
  pending                 MeasurementRow[]          (capped; oldest dropped first)
  enabled                 bool                      (default true; §9)

MeasurementRow = ActiveDay | FeatureDay | TaskOutcome | ExposureDay
  # every variant carries a date and nothing that identifies a device

# Backend, Postgres
event_received            35-day retention, then deleted by a scheduled job
  date, kind, key, bucket, outcome, variant, experiment, platform, app_version
  # no user column exists — the absence is the schema, not an omission

event_daily               indefinite; what the weekly summary reads
  date, kind, key, variant, dimension values, count
  # rows below the k floor are suppressed at query time, not stored pre-suppressed
```

`UserPreferences` in [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md) gains one field under Safety / privacy — `measurement_enabled: bool` (default true) — and that doc's identity model gains a fourth kind of identity whose value is *none*, deliberately, so that the next doc to need a hiker's identity finds this one already answered.

## 11. Phased rollout

*Phase A was built in a different shape on 2026-10-27 (§0, #1902). The heartbeat, the ingest route with its rejection tests, the retention job, the k floor, the Settings switch and the Privacy Policy update all shipped, alongside six events carrying a sealed identifier and position that this phase did not have. Phases B to D are unbuilt.*

Ordered so the privacy machinery exists before the data does, which is the opposite of how this usually goes.

**Phase A — the heartbeat, and nothing else.** §2's four booleans, the ingest route with its rejection tests, the retention job, the k floor, the Settings switch, and the Privacy Policy update. Answers DAU/WAU/MAU and new-device counts, which is the stated minimum, and proves the collection path with a payload that could not leak anything if it tried.

**Phase B — features and outcomes.** §3's registry, counters and task outcomes, plus `screen_crashed`. Gated on the §7 rule being real: a feature enters the registry when its design doc names what success looks like. The first weekly summary is written here.

**Phase C — experiments.** Wire §5's `variant` and `exposure_day` to FEATURE_GATING.md's local evaluation, the aggregate arithmetic in `pipeline/`, and the `safety_surface` refusal in the manifest. FEATURE_GATING.md's Phase 3 is this phase seen from the other side; they are one piece of work, not two.

**Phase D — only if a real metric demands it.** The §5 escape hatch, and with it whatever of GrowthBook's analysis half becomes worth running. Reaching Phase D should require an argument, and this document is the place that argument gets written down.

## 12. What this changes elsewhere

- **[FEATURE_GATING.md](FEATURE_GATING.md) §6's taxonomy is replaced, not refined.** It proposed events carrying `user_id`, `club_id`, `hike_id | segment_id` and a timestamp — a stable identifier next to a trail position and a time, which is the exact pair [#252](https://github.com/OurHike/OurHike/issues/252) removed from the report API three days before this was written. Nothing was wrong with the *questions* it wanted answered; §2, §3 and §5 answer all four of them without the identifier. That doc's fourth open question is answered here and its §6 now points here instead of specifying its own shape.
- **[TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md)'s "Nothing is recorded" stands for v1 and stands permanently for error *detail*.** What v2 adds is a count with no message and no stack (§3).
- **[IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md)** gains measurement as the identity that is deliberately absent, and one preference field.
- **The Privacy Policy's "Usage analytics" paragraph** is rewritten in the change that ships Phase A, per the promise it already carries.

## Open questions (for you, not decided here)

- ~~**Default on or default off.**~~ **Answered 2026-10-27 (§0): split** — counts on by default, linking the account asked once. §9 recommended on for a payload with no identifier and no location, because opt-in measurement at this scale returns a sample too small and too skewed to act on — which is collection with the privacy cost and none of the benefit. It is still a values call rather than a technical one, and [OurHikeValues.md](../OurHikeValues.md) #1 could be read either way.
- ~~**k = 25 against a beta that may not reach it.**~~ **Answered 2026-10-27 (§0): 25 everywhere, "<25" shown, masked when a report is built.** A chapter with nine active devices produces nothing but suppressed cells, and the temptation will be to lower the floor for exactly the breakdown that most needs it. Better answer is probably to compare clubs only on the aggregate and accept that per-chapter evidence arrives later, but that is worth deciding before the first person wants a number.
- **What counts as "active" on an iOS PWA**, where the app can be resumed by the OS without a hiker touching it. §2's definition is right; whether it is implementable there is a question for whoever writes it, and getting it wrong inflates DAU permanently and invisibly.
- ~~**Whether `club_id` may appear on aggregate rows at all.**~~ **Answered 2026-10-27 (§0): yes, on raw rows and aggregates alike, as the club whose trail the event is about.** FEATURE_GATING.md's per-chapter targeting wants the comparison; a club is also a place, and a place is the thing rule 2 keeps out. Aggregate-only plus the k floor is the proposed compromise, not a settled one.
- **Who reads the report, and what happens when nobody has for a month.** Still open: the report is generated by hand (§0), so nothing notices when nobody runs it. A metric nobody looks at is a privacy cost with no benefit on the other side of the ledger, and the honest response to that state is to switch the collection off, not to let it accumulate against a future that might want it. Worth agreeing in advance who notices.
