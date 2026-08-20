# OurHike — "It broke while I was out there" (v1, built)

Companion to [FEATURES.md](../FEATURES.md), [HIKER_SAFETY.md](HIKER_SAFETY.md) and
[IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md). Built for
**[#848 — The app breaking on the trail has no way back to us, and no way for us to
answer](https://github.com/OurHike/OurHike/issues/848)**.

This is the report a hiker files when **this software failed them while they were
relying on it**. It is not a bug report and it is not a trail report, and this
document exists mostly to say why it is neither.

---

## The gap it fills

**[#626 — A hiker who finds a bug in the app has nowhere in the app to report
it](https://github.com/OurHike/OurHike/issues/626)** built the "Report a bug" section
in Settings: four options, each an `<a href>` into a prefilled GitHub issue form. That
is the right mechanism for the four cases it covers, and `screens/ReportBug.tsx` is
honest in writing about what it costs:

> Each of these opens GitHub in your browser, so they need signal. Out of range, write
> down what happened while you can still see it.

Three things about the app failing on the trail break every assumption underneath
those four links:

1. **It happens where there is no signal.** The whole rest of the app queues writes in
   an outbox for exactly this reason. Until #848, the bug path was the part that did
   not — so the app's worst failure mode arrived at the one moment none of its report
   links worked.
2. **We would want to answer, and a public tracker is not a reply channel.** A GitHub
   issue reaches somebody only if that somebody has a GitHub account and filed under
   it. `bug_report.yml`'s Safety checkbox — "tick this and it gets looked at first" —
   is a promise about our reading order, not about ever getting back to anyone.
3. **A contact detail cannot go where the other four go.** A GitHub issue is public and
   permanent. [CONTRIBUTING.md](../CONTRIBUTING.md)'s "a commit is a publication that
   cannot be retracted" is the same argument, and `lib/bugReport.ts` already declines
   to attach `navigator.userAgent` on the far weaker ground that the device "is a fact
   about them".

## What ships

A fifth row at the **top** of "Report a bug", drawn unlike the four below it, opening a
screen rather than a browser tab.

| | The four GitHub options | This |
|---|---|---|
| Destination | A public issue on the tracker | A private table on this project's own backend |
| Needs signal | Yes | No — queues in the outbox |
| Needs an account | A GitHub one | None |
| Can carry a contact detail | No | Yes, and that is the point |
| Who reads it | Whoever watches the tracker | Whoever maintains OurHike, first |

**The form asks four things and takes one.**

- *What happened?* — the only required field. A report with nothing here is not a
  report.
- *Where were you, and when?* — free text: "mi 1,407", "the ford below Fontana", "no
  idea, somewhere in the Whites".
- *How can we reach you?* — free text, optional, unparsed. An email, a phone number, a
  forum handle, "I'm at Standing Bear Friday". Anything that constrained the shape
  would be a way of refusing a contact detail somebody offered.
- *Did it come close to any of these?* — four checkboxes, the four harms
  [CLAUDE.md](../CLAUDE.md) names: lost, out of water, in front of something dangerous,
  unable to get off the trail quickly. Ticking none is a complete answer.

What is attached without being typed: the build (`lib/buildInfo.ts`), and whether the
phone thought it was offline while the report was being written.

## The decisions worth disagreeing with

### Location is asked for, not taken

The app holds a GPS fix and a snapped trail mile, and either would be more precise than
anything typed into a box. Neither is attached.

`lib/bugReport.ts` already set this line, refusing to attach `navigator.userAgent` to a
public issue on the grounds that "the device is a fact about them, and this app does
not put facts about them anywhere they did not choose to put them". A location is a
stronger fact about them than a user-agent string, and this destination is private
rather than public — so this is a case where the *existing* rule would have permitted
taking it and the answer is still no. Silently attaching where somebody was, to a
report they wrote while frightened, is not a thing to do to save them typing.

Whether the offline flag belongs on the other side of that line is a fair question. It
is attached because it is a fact about the app's operating conditions rather than about
the person, because `bug_report.yml` already asks for it in words, and because for this
class of failure it is nearly always the answer.

It is also **asymmetrically reliable, and should be read that way**: `true` is
trustworthy, and `false` is `navigator.onLine`'s optimism — `lib/useOnline.ts` already
says that it "reports a captive portal or a bar of signal that carries no data as
online". A `false` on one of these rows means the phone believed it had a connection,
not that a request would have succeeded. Both column comments say so, because a field
attached on somebody's behalf should not be the one nobody knows the limits of.

### No account, which makes this the first unauthenticated write

Every other write in this backend is behind `get_current_user`. `POST /app-failures` is
not, because browsing the map has never needed an account and the hiker whose app just
failed may never have made one. Requiring one first is a way of not hearing from them.

**What that costs, said plainly: this is the first write endpoint an abuser can reach
without an account, and nothing rate-limits it.** A proxy-level limit is the natural
home and no claim is made that one exists today. The bound that does exist is on size,
not on rate. Before this path is load-bearing, somebody should decide what throttles it.

### The endpoint refuses almost nothing, on purpose

A 422 from this endpoint does not bounce a request. `lib/api.ts`'s
`permanentFailureReason` marks any 422 that does not name `authored_at` as permanent,
and `flushOutbox` then stops retrying that item — so a refusal here is the report never
arriving, for the class of report whose entire purpose is that somebody hears about it.

So `schemas/app_failure.py` truncates and drops rather than raising:

- Over-long text is cut to its cap. Somebody who wrote two thousand words about nearly
  walking off a ledge loses the tail, not the report.
- A `harms` value this server does not recognise is dropped and the rest kept. An older
  deployment meeting a newer client keeps the four it understands.
- A future-dated `authored_at` is accepted, unlike `POST /reports`, which refuses one.
  That refusal is right for a condition report — a maintainer reading a queue by time
  is misled by a backdated blowdown — and wrong here: nothing sorts this table by the
  hiker's claim, `received_at` is the server's own truth beside it, and the cost of
  being strict is losing the report over a wrong phone clock.

The caps themselves are **@unvalidated** — picked, not measured. 8,000 characters for
the description is twice `NoteText`'s, on the reasoning that this is somebody
describing an incident rather than labelling a blowdown; 500 for the two short fields
is a generous line. Real reports from real hikers would settle both. Being wrong about
them costs a tail rather than a report, which is why truncation rather than refusal is
what enforces them.

### Nothing reads the table back

There is no `GET`. No list, no detail, no moderation screen. A maintainer reads these
rows with psql.

That is the cheapest possible guarantee about a column holding a contact detail
somebody handed over while shaken: nothing serves it, so there is nothing to get wrong
about who may see it. A read endpoint added later has to break
`test_there_is_no_way_to_read_these_back` first — which is the point at which somebody
has to answer "who may read a stranger's phone number, and how is that checked".

The acknowledgement the sender gets back carries the id they already sent and the
arrival time, and nothing else.

### A separate table, not an eighth `ReportType`

A `Report` is about the trail: public by default, carrying a location and a mile so it
can be drawn as a pin, moving through the moderation queue closures and warnings share.
An `AppFailure` is about this software: drawn nowhere, moderated by nobody, and
carrying `contact`.

Folding them together would have put a contact detail on the model `ReportOut`
serialises to anonymous callers — one forgotten field away from exactly the leak
[#252](https://github.com/OurHike/OurHike/issues/252) closed. Two tables means that
mistake is not available to make.

## The path, end to end

```
screens/ReportBug.tsx        the row, above the four GitHub links
  → screens/AppFailureReport.tsx   the form, and its acknowledgement
  → lib/outbox.ts                  enqueueAppFailure - the queue's third cargo
  → lib/outboxSync.ts              flushes even when signed out, for this cargo only
  → lib/api.ts                     sendAppFailure → POST /app-failures, token optional
  → backend/app/routers/app_failures.py
  → app_failures                   RLS-locked, served by nothing
```

The outbox's four properties hold for this cargo exactly as they do for a blowdown: the
authored time travels, a failed send leaves the item queued, the id makes a resend
recognisably the same report, and a report written during a flush survives it. See
`lib/outbox.ts` for what each of those is worth.

## What this does not do

- **It does not tell the hiker anything back.** `answered_at` exists on the row and
  nothing writes it; a maintainer who answers a report stamps it by hand. There is no
  in-app thread, no status, no "we're looking at it". Whether there should be is a real
  product question and this is not it.
- **It does not detect anything.** A hiker has to notice the app failed and go looking
  for where to say so. The app has no idea it broke, which is precisely why this exists.
- **It does not replace the four GitHub options**, and should not. A misdrawn icon
  belongs on the public tracker where somebody can fix it.
- **It does not delete anything, ever.** See below.

## Open questions

- **Retention.** A contact detail is kept until somebody deletes the row, and nothing
  deletes rows. The form says only that the maintainers see it — which is true and is
  not a retention promise, because there is no policy to promise. What would settle
  this is a decision about how long a report stays reachable after it is answered, and
  the same question for the report body itself.
- **Whether a contact detail should be required.** It is not, today. Requiring one
  suppresses reports from people who will not give one; not requiring it means the
  report this project most wants to answer may arrive unanswerable. The form's
  acknowledgement says which of the two happened, which is the honest halfway house and
  not a resolution.
- **What throttles the endpoint.** See "No account" above.
- **Whether a hiker should be able to see their own filed reports.** They cannot. The
  reporter's own queue (`lib/reportStatus.ts`) covers condition reports and not this,
  and giving this one a read path reopens the question the "nothing reads it back"
  decision closes.
