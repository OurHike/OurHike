# OurHike — Authentication (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Also underpins [ACCOUNT_SYNC.md](ACCOUNT_SYNC.md) (what an account is *for* on a second device, and the account-deletion path this doc does not have), [SEGMENTS.md](SEGMENTS.md) (cross-device sync), [VOLUNTEERING.md](VOLUNTEERING.md) (club admin access), [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) (reporter identity/spam prevention), [MAP_OPTIONS.md](MAP_OPTIONS.md) (who can mark a trail closure), and [HIKER_SAFETY.md](HIKER_SAFETY.md) (the per-user comment-anonymity window) - all five raised a version of "we'll need some identity eventually" as an open question. This is that answer. [ONBOARDING.md](ONBOARDING.md) is where a trail name first gets collected - locally at first, becoming a real `User.display_name` only once linked to an account here. [COMMUNITY_BUILDING.md](COMMUNITY_BUILDING.md) (Tramily groups, check-ins, mentions) needs real, mutually-verifiable accounts throughout - none of it works on a device-local anonymous ID alone. See [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md) for how this model relates to the trail name, anonymity window, and check-in privacy designs across those docs. [PRICING_MODEL.md](PRICING_MODEL.md)'s `Entitlement` (which tier a hiker has, granted by purchase or by a club admin) extends this `User` record directly, rather than a separate billing identity.

**Scope revised 2026-07-28: moved into v1 MVP.** Originally scoped Post-MVP-but-build-first, since FEATURES.md's MVP was deliberately "no-account-needed" and none of the original MVP features (trail line, water, shelters, GPS, search) needed per-user state. **That's still true for browsing** - viewing the map, water, shelters, elevation profile, and even closures/warnings themselves still needs no account. What changed: [MAP_OPTIONS.md](MAP_OPTIONS.md)'s trail closures and [HIKER_SAFETY.md](HIKER_SAFETY.md)'s serious warning pins/wrong-way alert both moved into MVP too, and both need someone identifiable to mark, verify, or moderate them - so this can no longer wait for Segments/Volunteering/Report a Problem's Post-MVP timeline. Full breadth (Google/Apple/email, MFA) ships as designed below, not a stripped-down stopgap version.

---

## Sign-in methods

- **Google Sign-In.** No cost, at any usage level - confirmed directly against Google's own Identity Services docs.
- **Apple Sign-In.** No *marginal* cost beyond the $99/yr Apple Developer Program membership already required (and already budgeted, ROADMAP.md Phase 3) to ship on iOS at all. Worth knowing precisely: Apple's App Store Review Guideline 4.8 ("Login Services") requires any app offering a third-party/social login (Google Sign-In counts) to also offer an equivalent, privacy-respecting alternative - limited data collection, private-email option, no ad tracking without consent. Sign in with Apple exists specifically to satisfy this, so once Google Sign-In ships on iOS, this stops being "preferred" and becomes close to mandatory for App Store approval. (The email/password option below might independently satisfy 4.8 on its own merits, but Apple's review is case-by-case - not worth relying on that interpretation holding.)
- **Email.** Two ways in, and the ordering between them is a decision rather than a preference.

  **An emailed sign-in link is the default.** It is one field, there is nothing to set now and nothing to recall six weeks up the trail from where it was set, and following the link is itself proof the address belongs to whoever asked - so it satisfies the verification requirement below directly instead of by a separate confirmation step. It also creates the account when the address is new, which removes the "sign up or sign in?" question from in front of the form entirely.

  **A password stays available underneath it.** A link has a cost this app feels more than most applications do: it sends someone out to an email client and asks them to come back, and on a ridge with one bar that round trip is the fragile part of the whole flow. Someone who set a password can finish without leaving the app. Password hashing is the auth provider's job either way (see "Technical approach" - this should never be hand-rolled, see why below).

A user can have more than one of these linked to the same account (e.g. signed up with email, later added Google) - worth designing for from the start rather than retrofitting.

## Verification requirements

- **At account creation:** email must be verified (confirmation link or code) before the account is treated as fully active. The sign-in link satisfies this inherently - following it *is* the verification, and there is no window in which an unverified account exists. The email/password path needs the separate confirmation step, and Supabase withholds the session until it is done. Google/Apple sign-in already verify the email on their end, so that is a Provider fact to trust, not a second check to bolt on.
- **On email change:** the same verification flow runs again, sent to the *new* address, and the account's email of record doesn't change until that's confirmed. Standard practice alongside this: notify the *old* address that a change was requested, so an account takeover attempt doesn't happen silently.

## MFA - recommended as optional, not mandatory

Worth offering, not worth requiring. The deciding factor is really cost-to-build rather than "should we have it": with an auth provider that supports TOTP (authenticator-app) MFA natively (see below), turning it on as a user-enabled setting costs very little extra engineering - so there's little reason to leave it out entirely. Requiring it for everyone would add real friction to a use case whose whole point is fast, low-friction access to safety info on the trail (the same UX principle that kept the MVP account-less in the first place) - that cost isn't worth paying for users who don't want it.

## Technical approach - recommendation, not a mandate

**Don't hand-roll this.** Password hashing, session/token management, OAuth token exchange, and MFA are all notoriously easy to get subtly wrong, and authentication bugs are a different category of risk than most - this is exactly the kind of "undifferentiated heavy lifting" better handled by a well-established provider than reinvented by a volunteer-run project (value #8 - sustainable, not just launched).

**Recommendation: Supabase Auth**, for a specific reason beyond "it's a popular option" - it fits this project's *existing* plan unusually well:

- TECHNICAL_ARCHITECTURE.md already specifies **Postgres** for the Phase 2+ backend. Supabase's core product *is* Postgres + Auth (+ storage/realtime) as one coherent package - this isn't introducing a new database choice alongside a separate auth vendor, it's getting the database already planned and a mature auth layer together.
- It's **open source** (including the Auth service itself, GoTrue) and self-hostable - unlike Firebase, Auth0, or Cognito, all closed/proprietary. That matters directly for value #3 (open by default) and value #7 (inheritable, no vendor lock-in "including our own," per value #6) - if Supabase's hosted offering ever stopped being the right fit, the same open-source service can be self-hosted rather than forcing a rewrite. That's the actual safety net those values ask for, not just a preference for open-source branding.
- It supports Google/Apple OAuth, email/password with verification, and TOTP MFA out of the box - everything above, without custom code for any of it.
- It has a generous free tier at this project's likely early scale (worth checking their current pricing page before committing - tiers change - but historically comfortable for a project this size).
- Practical note: this session's environment already has Supabase MCP tooling connected, which made checking this recommendation concretely easy - a small, real signal this fits where things already are, not just an abstract choice.

**Looking further down the roadmap - external system connections (e.g. NYNJTC systems):** this is exactly why the provider choice matters now even though nothing here is being built yet. Supabase Auth supports SSO via SAML/OIDC on top of its regular auth (a paid-tier feature, not built into the free tier) - meaning if/when a real need to federate with an external club or organization's identity system shows up, there's a concrete path that doesn't require migrating auth providers first. Nothing to build today - just worth knowing the foundation has room for it.

## What the client does with this

The recommendation above is now built on both sides, and the split matters for reading the code: **Supabase Auth is a separate service from this project's own backend.** Signing in never needed the backend deployed - only a project to sign in to. Sending what a signed-in hiker contributes still does.

- `client/src/lib/supabase.ts` - the client, behind the same build-time-config shape `lib/config.ts` uses for the data bucket. An unconfigured build gets a null client rather than one that fails at its first request, so the app runs exactly as before with the sign-in controls saying so.
- `client/src/lib/auth.ts` - sign-in per provider, sign-out, and the session-to-account adaptation. Nothing here implements authentication; it adapts what Supabase returns.
- `client/src/lib/useAuth.ts` - the account as React state. It subscribes rather than only asking once, because an OAuth round trip finishes by loading the page again, not by resolving a promise in the tab that left.
- `client/src/screens/EmailSignIn.tsx` - the one provider that needs a screen. Google and Apple need no UI beyond their button. It opens on the link path and keeps the password path one tap away, per the ordering argued above.

**The provider set is build configuration** (`VITE_AUTH_PROVIDERS`, defaulting to Google alone since [#397](https://github.com/OurHike/OurHike/issues/397) decided v1's set). The three do not cost the same to switch on - email needs nothing, Google needs a Cloud Console registration, Apple needs the $99/yr membership - and a button whose credentials do not exist reaches an error page rather than an account. `SignInPrompt` still defaults to all three, so the wireframe's answer stays the component's; narrowing is something a deployment does.

That default was `google,email` until #397, and the correction is worth keeping because the reasoning that produced it was sound and still wrong. Email *is* the cheapest of the three to switch on, which is what put it in the default - but cheap setup and working delivery are different claims, and Supabase's built-in sender is not one this project ships on. The result was a default that offered a sign-in which could not complete, which is the same failure as an unconfigured provider, arrived at from the opposite direction. Apple is deferred to v2 ([#92](https://github.com/OurHike/OurHike/issues/92)); email returns when it has a sender behind it.

**Creating an account is not signing in.** Supabase withholds the session until the emailed confirmation link is followed, so the email screen has a third outcome besides success and failure. Collapsing that into "signed in" would leave someone waiting to send a contribution that never would.

Two things named in this doc are **not** built: MFA, and the multiple-providers-one-account linking below. Both are Supabase settings rather than client code, but neither has been turned on or exercised.

## Data model sketch

```
User
  id
  email, email_verified (bool), email_verified_at
  linked providers: [google, apple, email]  (a user may have more than one)
  password_hash (only relevant if "email" is a linked provider)
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
  is a credential that can act as any user. So after an OurHike deletion, the email address,
  password hash and linked providers sketched in the data model above are still in Supabase
  Auth, and the hiker's existing session is still valid; the check in the previous point is
  what makes that session useless rather than a way straight back into the account. Closing
  it properly is ACCOUNT_SYNC.md's open decision 5, and it is a decision about blast radius
  rather than about deletion.

## Open questions (for you, not decided here)

- **Exact provider pricing at real scale.** The free-tier framing above is directionally right but worth confirming against Supabase's current pricing before this gets built, not assumed from this doc.
- **What "account" actually unlocks first.** This doc is the identity layer, not the features built on it - Segments sync, Volunteering's admin roles, and Report a Problem's reporter identity are three separate follow-on decisions about what an account *does*, not addressed here.
- **Self-hosting Supabase vs. using their hosted service.** Recommended above as "hosted for now, self-hostable later if ever needed" rather than a today decision - worth confirming that's the right default rather than something to decide now.
