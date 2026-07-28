# OurHike — Authentication (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Also underpins [SEGMENTS.md](SEGMENTS.md) (cross-device sync), [VOLUNTEERING.md](VOLUNTEERING.md) (club admin access), [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) (reporter identity/spam prevention), [MAP_OPTIONS.md](MAP_OPTIONS.md) (who can mark a trail closure), and [HIKER_SAFETY.md](HIKER_SAFETY.md) (the per-user comment-anonymity window) - all five raised a version of "we'll need some identity eventually" as an open question. This is that answer.

**Scope decided 2026-07-28: Post-MVP, but build it first.** FEATURES.md's v1 MVP is deliberately "no-account-needed" (a stated UX principle, tied to value #1) - none of the core MVP features (trail line, water, shelters, GPS, search) need per-user state. The need here comes entirely from the three Post-MVP features above, so this doesn't jump the MVP queue. It should, however, be the **first** Post-MVP feature actually built, since all three others depend on it to reach their real versions rather than a stopgap (a device-local anonymous ID, client-only storage, etc.).

---

## Sign-in methods

- **Google Sign-In.** No cost, at any usage level - confirmed directly against Google's own Identity Services docs.
- **Apple Sign-In.** No *marginal* cost beyond the $99/yr Apple Developer Program membership already required (and already budgeted, ROADMAP.md Phase 3) to ship on iOS at all. Worth knowing precisely: Apple's App Store Review Guideline 4.8 ("Login Services") requires any app offering a third-party/social login (Google Sign-In counts) to also offer an equivalent, privacy-respecting alternative - limited data collection, private-email option, no ad tracking without consent. Sign in with Apple exists specifically to satisfy this, so once Google Sign-In ships on iOS, this stops being "preferred" and becomes close to mandatory for App Store approval. (The email/password option below might independently satisfy 4.8 on its own merits, but Apple's review is case-by-case - not worth relying on that interpretation holding.)
- **Email + password.** The plain option requested - standard email/password, with password hashing handled by whatever auth provider is chosen (see "Technical approach" - this should never be hand-rolled, see why below).

A user can have more than one of these linked to the same account (e.g. signed up with email, later added Google) - worth designing for from the start rather than retrofitting.

## Verification requirements

- **At account creation:** email must be verified (confirmation link or code) before the account is treated as fully active. Applies to the email/password path directly; Google/Apple sign-in already verify the email on their end, so this is a Provider fact to trust, not a second check to bolt on.
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

## Data model sketch

```
User
  id
  email, email_verified (bool), email_verified_at
  linked providers: [google, apple, email]  (a user may have more than one)
  password_hash (only relevant if "email" is a linked provider)
  mfa_enabled (bool)
  created_at

EmailChangeRequest
  user_id, new_email, verification_sent_at, confirmed_at
  (old email stays of record, and gets a heads-up notification, until confirmed)
```

## Open questions (for you, not decided here)

- **Exact provider pricing at real scale.** The free-tier framing above is directionally right but worth confirming against Supabase's current pricing before this gets built, not assumed from this doc.
- **What "account" actually unlocks first.** This doc is the identity layer, not the features built on it - Segments sync, Volunteering's admin roles, and Report a Problem's reporter identity are three separate follow-on decisions about what an account *does*, not addressed here.
- **Self-hosting Supabase vs. using their hosted service.** Recommended above as "hosted for now, self-hostable later if ever needed" rather than a today decision - worth confirming that's the right default rather than something to decide now.
