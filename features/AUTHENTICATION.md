# OurHike — Authentication (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Also underpins [ACCOUNT_SYNC.md](ACCOUNT_SYNC.md) (what an account is *for* on a second device, and the account-deletion path this doc does not have), [SEGMENTS.md](SEGMENTS.md) (cross-device sync), [VOLUNTEERING.md](VOLUNTEERING.md) (club admin access), [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) (reporter identity/spam prevention), [MAP_OPTIONS.md](MAP_OPTIONS.md) (who can mark a trail closure), and [HIKER_SAFETY.md](HIKER_SAFETY.md) (the per-user comment-anonymity window) - all five raised a version of "we'll need some identity eventually" as an open question. This is that answer. [ONBOARDING.md](ONBOARDING.md) is where a trail name first gets collected - locally at first, becoming a real `User.display_name` only once linked to an account here. [COMMUNITY_BUILDING.md](COMMUNITY_BUILDING.md) (Tramily groups, check-ins, mentions) needs real, mutually-verifiable accounts throughout - none of it works on a device-local anonymous ID alone. See [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md) for how this model relates to the trail name, anonymity window, and check-in privacy designs across those docs. [PRICING_MODEL.md](PRICING_MODEL.md)'s `Entitlement` (which tier a hiker has, granted by purchase or by a club admin) extends this `User` record directly, rather than a separate billing identity.

**Scope revised 2026-07-28: moved into v1 MVP.** Originally scoped Post-MVP-but-build-first, since FEATURES.md's MVP was deliberately "no-account-needed" and none of the original MVP features (trail line, water, shelters, GPS, search) needed per-user state. **That's still true for browsing** - viewing the map, water, shelters, elevation profile, and even closures/warnings themselves still needs no account. What changed: [MAP_OPTIONS.md](MAP_OPTIONS.md)'s trail closures and [HIKER_SAFETY.md](HIKER_SAFETY.md)'s serious warning pins moved into MVP too (the wrong-way alert moved with them at the time, before its later removal - #93/#308), and closures and warning pins both need someone identifiable to mark, verify, or moderate them - so this can no longer wait for Segments/Volunteering/Report a Problem's Post-MVP timeline. Full breadth (Google/Apple/email, MFA) ships as designed below, not a stripped-down stopgap version.

---

## Sign-in methods

- **Google Sign-In.** No cost, at any usage level - confirmed directly against Google's own Identity Services docs.
- **GitHub Sign-In** (added 2026-09-17, [#1572](https://github.com/OurHike/OurHike/issues/1572)). No cost: a GitHub OAuth app is free to register, and Supabase's GitHub provider takes its client id and secret. It asks GitHub for the `user:email` scope and keys the account on the primary verified address, so the same hiker signing in with Google one day and GitHub the next lands in one account (see "one account, several doors" below); a GitHub account with no verified email cannot sign in at all, which is one of the refusals #1573 is about. One thing to know that Google does not have: a GitHub OAuth app takes exactly one callback URL, so production and UA each need an app of their own.
- **Apple Sign-In.** No *marginal* cost beyond the $99/yr Apple Developer Program membership already required (and already budgeted, ROADMAP.md Phase 3) to ship on iOS at all. Worth knowing precisely: Apple's App Store Review Guideline 4.8 ("Login Services") requires any app offering a third-party/social login (Google Sign-In counts) to also offer an equivalent, privacy-respecting alternative - limited data collection, private-email option, no ad tracking without consent. Sign in with Apple exists specifically to satisfy this, so once Google Sign-In ships on iOS, this stops being "preferred" and becomes close to mandatory for App Store approval. (The email/password option below might independently satisfy 4.8 on its own merits, but Apple's review is case-by-case - not worth relying on that interpretation holding.)
- **Email.** One way in, decided 2026-09-17 ([#279](https://github.com/OurHike/OurHike/issues/279), [#1572](https://github.com/OurHike/OurHike/issues/1572)): **a 6-digit code, emailed and typed into the app.** Not a link and not a password, and the two earlier versions of this bullet are worth keeping in one sentence each, because each was replaced for a reason that still holds.

  *A link was the default* because it is one field with nothing to remember and following it proves the address. Its cost is that it sends someone out to a mail app and asks them to come back, and on a phone the link opens the browser rather than the installed app, so the session can land where the app cannot see it. *A password stayed underneath it* so that someone could finish without leaving the app; its cost is that it has to be set now and recalled six weeks up the trail, and a password reused from a breached site is exactly as safe as that site - the one check that catches those is a paid-plan feature (LAUNCH_CHECKLIST.md 5a).

  A code has the property the password was kept for - the sign-in finishes inside the app - with none of either cost: nothing to remember, nothing to leak, and the session lands in the app's own storage because the request that earns it is made from there. Typing the code back is itself the proof the address belongs to whoever asked, so it satisfies the verification requirement below directly. It also creates the account when the address is new, which removes the "sign up or sign in?" question from in front of the form entirely. It is the one door that works inside the Capacitor shells with no redirect (#1396).

  **What it needs that the others do not is a sender.** Supabase's built-in mailer sends 2 messages an hour, only to the project's own team, and refuses everyone else - which is why email was taken out of v1's default set (#397) and why the build's provider list is not the switch that turns it on. LAUNCH_CHECKLIST.md 4.3c and 4.3d are the sender (custom SMTP through Resend) and the templates (`{{ .Token }}` in both "Magic Link" and "Confirm sign up", since a new address gets the second). `backend/check_supabase_config.py` reads both back.

**One account, several doors.** Supabase links a new identity to an existing user when the provider has verified the same email address - Google and GitHub both do, and the code does by construction - so a hiker who uses more than one of these has one account, one trail name and one set of reports. Observed once rather than assumed: the Google verification on #92 (2026-08-06) attached a `google` identity to an existing email user for the same address, two identities on one user, no duplicate. What has NOT been exercised is the direction Supabase refuses - an *unverified* email from a provider - which none of the three shipped providers can produce.

## Verification requirements

- **At account creation:** email must be verified before the account is treated as fully active. The emailed code satisfies this inherently - typing it back *is* the verification, and there is no window in which an unverified account exists. Google, GitHub and Apple sign-in already verify the email on their end, so that is a provider fact to trust, not a second check to bolt on.
- **On email change:** the same verification flow runs again, sent to the *new* address, and the account's email of record doesn't change until that's confirmed. Standard practice alongside this: notify the *old* address that a change was requested, so an account takeover attempt doesn't happen silently.

## MFA - recommended as optional, not mandatory

Worth offering, not worth requiring. The deciding factor is really cost-to-build rather than "should we have it": with an auth provider that supports TOTP (authenticator-app) MFA natively (see below), turning it on as a user-enabled setting costs very little extra engineering - so there's little reason to leave it out entirely. Requiring it for everyone would add real friction to a use case whose whole point is fast, low-friction access to safety info on the trail (the same UX principle that kept the MVP account-less in the first place) - that cost isn't worth paying for users who don't want it.

## Technical approach - recommendation, not a mandate

**Don't hand-roll this.** Password hashing, session/token management, OAuth token exchange, and MFA are all notoriously easy to get subtly wrong, and authentication bugs are a different category of risk than most - this is exactly the kind of "undifferentiated heavy lifting" better handled by a well-established provider than reinvented by a volunteer-run project (value #8 - sustainable, not just launched).

**Recommendation: Supabase Auth**, for a specific reason beyond "it's a popular option" - it fits this project's *existing* plan unusually well:

- TECHNICAL_ARCHITECTURE.md already specifies **Postgres** for the Phase 2+ backend. Supabase's core product *is* Postgres + Auth (+ storage/realtime) as one coherent package - this isn't introducing a new database choice alongside a separate auth vendor, it's getting the database already planned and a mature auth layer together.
- It's **open source** (including the Auth service itself, GoTrue) and self-hostable - unlike Firebase, Auth0, or Cognito, all closed/proprietary. That matters directly for value #3 (open by default) and value #7 (inheritable, no vendor lock-in "including our own," per value #6) - if Supabase's hosted offering ever stopped being the right fit, the same open-source service can be self-hosted rather than forcing a rewrite. That's the actual safety net those values ask for, not just a preference for open-source branding.
- It supports Google, GitHub and Apple OAuth, emailed one-time codes, and TOTP MFA out of the box - everything above, without custom code for any of it.
- It has a generous free tier at this project's likely early scale (worth checking their current pricing page before committing - tiers change - but historically comfortable for a project this size).
- Practical note: this session's environment already has Supabase MCP tooling connected, which made checking this recommendation concretely easy - a small, real signal this fits where things already are, not just an abstract choice.

**Looking further down the roadmap - external system connections (e.g. NYNJTC systems):** this is exactly why the provider choice matters now even though nothing here is being built yet. Supabase Auth supports SSO via SAML/OIDC on top of its regular auth (a paid-tier feature, not built into the free tier) - meaning if/when a real need to federate with an external club or organization's identity system shows up, there's a concrete path that doesn't require migrating auth providers first. Nothing to build today - just worth knowing the foundation has room for it.

## What the client does with this

The recommendation above is now built on both sides, and the split matters for reading the code: **Supabase Auth is a separate service from this project's own backend.** Signing in never needed the backend deployed - only a project to sign in to. Sending what a signed-in hiker contributes still does.

- `client/src/lib/supabase.ts` - the client, behind the same build-time-config shape `lib/config.ts` uses for the data bucket. An unconfigured build gets a null client rather than one that fails at its first request, so the app runs exactly as before with the sign-in controls saying so.
- `client/src/lib/auth.ts` - sign-in per provider (`signInWithProvider` for Google, GitHub and Apple; `sendEmailCode` and `verifyEmailCode` for email), sign-out, and the session-to-account adaptation. Nothing here implements authentication; it adapts what Supabase returns. `lib/authMessages.ts` is where Supabase's error strings become sentences a hiker can act on (#315), including the two that mean "this build has no sender".
- `client/src/lib/useAuth.ts` - the account as React state. It subscribes rather than only asking once, because an OAuth round trip finishes by loading the page again, not by resolving a promise in the tab that left - and a code verified in `EmailSignIn` lands through the same subscription, which is why `App.tsx` closes the sign-in flow on one signal for every door.
- `client/src/screens/EmailSignIn.tsx` - the one provider that needs a screen. Google, GitHub and Apple need no UI beyond their button. Two steps: the address, then the code, on one screen so the address is not typed twice and "send another code" is one tap. Neither step claims a sign-in; the session arriving is what closes it.

**The provider set is build configuration** (`VITE_AUTH_PROVIDERS`, defaulting to Google alone since [#397](https://github.com/OurHike/OurHike/issues/397) decided v1's set). The four do not cost the same to switch on - Google and GitHub each need a free OAuth registration, Apple the $99/yr membership, email a sender - and a button whose credentials do not exist reaches an error page rather than an account. `SignInPrompt` still defaults to all four, so the wireframe's answer (plus GitHub) stays the component's; narrowing is something a deployment does.

That default was `google,email` until #397, and the correction is worth keeping because the reasoning that produced it was sound and still wrong. Email *is* the cheapest of the providers to switch on, which is what put it in the default - but cheap setup and working delivery are different claims, and Supabase's built-in sender is not one this project ships on. The result was a default that offered a sign-in which could not complete, which is the same failure as an unconfigured provider, arrived at from the opposite direction.

**The deployed set is the `AUTH_PROVIDERS` repository variable, and #1572 makes it `google,github,email`** - after GitHub's OAuth app exists, custom SMTP is configured and both email templates carry the code, and *before* the config check that reads all of that back, because `backend/check_supabase_config.py` inspects the sender and the templates only for providers the variable names (LAUNCH_CHECKLIST.md 4.5). Setting it deploys nothing: a build reads it, and the next build is a push to `main` or a tag. The code default stays `google`, the one provider a fresh project can complete with a Cloud Console client and nothing else. Apple is deferred to v2 ([#92](https://github.com/OurHike/OurHike/issues/92)).

**Creating an account and signing in are one step.** With the code, a new address is created on the first `sendEmailCode` and signed in on `verifyEmailCode`, so the email screen has exactly two outcomes, a session or a refusal, and every refusal is a sentence on screen. The previous version of this paragraph explained a third outcome - an account created but unconfirmed, waiting on a link - which the code path does not have.

One thing named in this doc is **not** built: MFA, a Supabase setting that has not been turned on or exercised. The multiple-providers-one-account linking is Supabase's own behaviour on a verified email and has been observed once (above), not designed here.

## Data model sketch

```
User
  id
  email, email_verified (bool), email_verified_at
  linked providers: [google, github, apple, email]  (a user may have more than one)
  (no password_hash: the email provider is a one-time code, and no OurHike
   build has ever shipped a password path to a hiker - #279, #397)
  mfa_enabled (bool)
  display_name (the trail name from ONBOARDING.md, once linked to this account -
                not the real name from email/OAuth, per IDENTITY_AND_PRIVACY.md)
  created_at

EmailChangeRequest
  user_id, new_email, verification_sent_at, confirmed_at
  (old email stays of record, and gets a heads-up notification, until confirmed)
```

## Deleting an account (added 2026-08-22, #895)

This document was thorough about getting **in** — sign-in methods, verification, MFA — and
said nothing about getting out. That was harmless while every private thing a hiker owned
lived on their own handset, because uninstalling *was* deletion; it stopped being harmless
the moment [ACCOUNT_SYNC.md](ACCOUNT_SYNC.md)'s phases A and B put preferences and trips on
a server.

`DELETE /profiles/me` is the way out, and `GET /profiles/me/export` is the file a hiker
takes with them first. What goes, what stays, and why the line is where it is belongs to
[ACCOUNT_SYNC.md](ACCOUNT_SYNC.md) phase E and to
`backend/app/core/account_deletion.py`. Two consequences are this document's, because they
are about the identity layer rather than about the data:

- **A deleted account cannot be signed back into.** `core/auth.py` refuses any token whose
  profile row carries `deleted_at`, with a 401. Not belt-and-braces: see the next point.
- **The Supabase Auth user is NOT deleted, and this backend cannot delete it.** Deleting a
  user through Supabase's admin API needs a service-role key, and `app/config.py` holds
  only the anon key and the JWKS — deliberately, since a service-role key in this process
  is a credential that can act as any user. So after an OurHike deletion, the email address
  and linked providers sketched in the data model above are still in Supabase
  Auth, and the hiker's existing session is still valid; the check in the previous point is
  what makes that session useless rather than a way straight back into the account. Closing
  it properly is ACCOUNT_SYNC.md's open decision 5, and it is a decision about blast radius
  rather than about deletion.

## Open questions (for you, not decided here)

- **Exact provider pricing at real scale** - answered on [#1572](https://github.com/OurHike/OurHike/issues/1572), from the vendors' own pages on 2026-09-17: Supabase Free is $0 with 50,000 monthly active users, custom SMTP included; Pro is $25/month per organisation with 100,000 MAU then $0.00325 each; Google and GitHub sign-in cost nothing; the sender (Resend) is $0 for 3,000 emails a month and 100 a day, then $20/month for 50,000. The meter is per active user and provider-blind (#393). What would move this project to Pro is not authentication but backups, which Free does not have and ACCOUNT_SYNC.md's server-side trips now need.
- **What "account" actually unlocks first.** This doc is the identity layer, not the features built on it - Segments sync, Volunteering's admin roles, and Report a Problem's reporter identity are three separate follow-on decisions about what an account *does*, not addressed here.
- **Self-hosting Supabase vs. using their hosted service.** Recommended above as "hosted for now, self-hostable later if ever needed" rather than a today decision - worth confirming that's the right default rather than something to decide now.
