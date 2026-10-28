# Site Remediation: privacy statement

**A draft for the maintainer, written 2026-10-28 at the maintainer's request.**
Nothing in it has been reviewed, and the app does not link to it yet. The places marked
**[to fill]** are facts this draft cannot know. Everything else is what the code in
`apps/remediation/` does today, and each section names where.

---

## Who runs this

Site Remediation is run by **[to fill: the person or organisation responsible, and an
address for privacy questions]**. It is a separate app from OurHike, but it uses
OurHike's sign-in, so your account is your OurHike account.

## What we keep, and why

**Your account.** When you sign in with a code sent to your email address, OurHike's
Supabase project keeps your email address and an account id. This is the same account
you would use on OurHike. Site Remediation itself keeps only the account id.

**What you choose to give.** Each of these is kept with your account id, in the
`remediation` schema (`apps/remediation/db/`):

- **A display name**, if you set one. It is optional.
- **Lists of sites** you make, and the share links you create for them.
- **Changes you make to a club's ranking weights**, with your name as it was at the time.
- **The sites you claim:**
  - when you claimed each site, and the steps you ticked as done;
  - your notes and your hours;
  - the photos you take there.
- **The follow-up visits you take.**

**Photos.** Your phone redraws every photo before sending it. That removes the location
and camera details a phone writes into a photo (`web/src/photo.ts`). Keep people out of
the frame: the app asks you to, but it cannot check.

**What we do not collect.** The app never asks for your location; its pages forbid it
(`web/headers.ts`). It uses no analytics and no advertising.

## What is public

Site Remediation is meant to be open data. **Work is public as soon as you mark it
done** (decided by the maintainer, 2026-10-28). Anyone, signed in or not, can then see
that work's:

- **record:** the site, the dates, the steps you ticked, your notes and your hours;
- **photos:** the before and after photos, and any extra ones;
- **name:** your display name, if you set one.

Until you mark a claim done, other people see only that the site is claimed and when the
claim ends, **not who claimed it** (decided 2026-10-27).

Also public:

- every follow-up visit: when it opens and how it stands;
- every change to a club's ranking weights, with the changer's name.

All of this is published each day as files anyone can download (CSV and Parquet), and
through Supabase's public interface. A published photo comes with a link that works for
eight days. Anyone can make a new link to a public photo, and a link someone has made
keeps working until it expires, even if the photo is later removed.

## Who else handles your data

| Service | What it handles |
|---|---|
| **Supabase** (OurHike's project) | Your account, everything listed above, and the photos |
| **Cloudflare Pages** | Hosts the app. Like any web host, it sees your IP address when you load the app |
| **OpenFreeMap** | Draws the map. Your browser asks it for map tiles, which shows it your IP address and the area you are looking at |
| **Google Fonts** | Serves the app's typefaces. Your browser asks it for them, which shows it your IP address |

**[to fill: whether any of these hold data outside the United States, and on what
terms, once the maintainer has checked each provider's terms.]**

## On your phone

To work with no signal, the app keeps some things on your phone, in your browser's
storage, under your account:

- the claims you open;
- photos waiting to be sent, and photos the server refused, until you decide what to do
  with them;
- the photos you have viewed;
- your checklist ticks.

Signing out deletes the claims and photos it kept, after warning you about any photos
not yet sent.

**Signing out signs you out everywhere**, on every device, including OurHike (decided
2026-10-28). With no signal, it can sign out only the phone you are holding until there
is signal again.

## How long we keep it

- **Done work and its photos: for good**, as the record of the site (decided
  2026-10-28).
- **Claims released or run out:** the claim record stays, for good. Its photos stay in
  storage too, and only you can see them, because they were never made public.
- **Photos uploaded but never added to a claim:** they stay in storage, and nobody can
  see them.

There is no automatic clean-up of storage yet (PLAN.md §11).

## Deleting your data

Under your account, **Delete my Site Remediation data**:

- **deletes:** your display name (also from the weights history), your lists and your
  hours;
- **releases:** any site you still hold;
- **keeps, without your name:** the work you finished and the weight changes you made,
  because they are each site's and each club's history.

Signing in again starts an empty account.

This does not delete your OurHike account or your email address; that is OurHike's to
do (**[to fill: how, under OurHike's own privacy policy]**).

## Children

**[to fill: a minimum age, if any. Volunteer work through a maintaining club usually
has one.]**

## Changes

**[to fill: how changes to this statement will be announced.]**
