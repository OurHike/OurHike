# OurHike — Project Values

## Why this document exists

Before we build features, we're writing down what OurHike is *for* and what it should never become. Avenza's shutdown is the trigger, but the deeper opportunity is to build something that belongs to the hiking community, not a vendor — as durable and community-owned as the trails themselves.

These values guide feature decisions, technical tradeoffs, and governance choices as the project grows. When we're unsure how to proceed, this is where we come back to.

---

## 1. Hike your own hike

The app should support many different ways of hiking, not push people toward one "correct" way. A day-hiker checking conditions before a Bear Mountain loop and a section-hiker planning three weeks of the AT are both fully served — neither is a lesser use case. We design for autonomy: give people accurate information and good tools, then get out of the way. We avoid prescriptive gamification, forced social features, or anything that implies there's a "right" way to hike.

## 2. Built by the community that built the trail

NYNJTC volunteers cut the first mile of the Appalachian Trail in 1923, at Bear Mountain, and volunteers have maintained it ever since. OurHike works the same way: conditions, corrections, and improvements come from hikers and maintainers on the ground, not a company's survey team. The app is infrastructure for a volunteer culture that already exists, not a replacement for it.

## 3. Open by default

Source code, data formats, and — wherever legally and safely possible — the underlying trail data should be open. This is what makes the project inheritable: Avenza's shutdown left NYNJTC stuck because the tool was closed, and OurHike should never do that to another club. If OurHike itself ever disappears, any club running it can fork the code and keep going.

## 4. Trustworthy above all — because lives depend on it

This is a safety tool as much as a convenience one. People will use it to decide which way at a junction, whether a crossing is passable, whether to push on before dark. Accuracy, clarity, and honesty about uncertainty (e.g., "reported 3 days ago" vs. "confirmed today") matter more than polish or feature count. A smaller feature set hikers can trust beats a flashy one they have to second-guess.

## 5. Free and accessible to every hiker

No paywalls on safety-relevant information — conditions, closures, hazards, and basic maps stay free, forever, for everyone. If paid tiers are ever needed for sustainability, they cover convenience features only, never core safety data. Staying safe on the trail shouldn't require a subscription.

## 6. Belongs to the trails, not the platform

Data portability is a first-class requirement, not an afterthought. Users and organizations can always export their data — routes, reports, maps — in open formats. We design against vendor lock-in, including our own. A tool the community can leave anytime is, paradoxically, one they'll want to stay with.

## 7. Built to be inherited

NYNJTC is the first user, not the only one. Every decision should ask: could another ATC-affiliated club pick this up with minimal friction? That means clear documentation, sane defaults, and no NYNJTC-specific assumptions baked into the architecture. We're building a shared tool that NYNJTC happens to need first, not a NYNJTC app other clubs might use.

## 8. Sustainable, not just launched

Volunteer-run nonprofits can't carry heavy infrastructure costs or maintenance burdens. We favor boring, well-supported technology over cutting-edge complexity, and design so the project can survive turnover in maintainers. Still running quietly in ten years beats launching impressively and then stalling out.

## 9. Be magical

Trail magic — hikers finding unexpected generosity or help exactly when they need it — is core to hiking culture. The ATC has written thoughtfully about what makes it work and what makes it backfire, and we want that same judgment built into OurHike, not just the word.

Real trail magic isn't about volume — it's the right thing showing up at the right moment, given with care for the person, the land, and the community. Unmanaged, generosity can tip into crowding, litter, habituated wildlife, or hikers losing the self-reliance that's part of the point of being out there. "Be magical" means designing for genuine, well-timed generosity while actively designing against the versions that cause harm:

- **Small, well-timed moments over broadcast events.** Help individual hikers connect with individual moments of help — a timely condition report, an offer, a fix — rather than amplifying large gatherings, a known source of overcrowding and habitat damage.
- **No unattended caches.** No feature should make it easy to broadcast "food left at mile X" pins. Unattended food and drink causes real harm — wildlife habituation, spoilage, litter, even legal trouble on public land. Point people toward in-person generosity instead.
- **Generosity toward the trail, not just around it.** Nudge behavior toward volunteering with trail-maintaining clubs, packing out trash, and supporting hiker-friendly local businesses — the forms of magic that sustain the Trail, not just the people passing through it.
- **Protect self-reliance.** Equip hikers to take care of themselves — accurate conditions, honest data, good planning tools — rather than create dependency on rescue or resupply by strangers. Magic is a gift you stumble into, not something to plan on.
- **Safety awareness on both sides.** Trail angels and hikers connecting through the app are still strangers meeting in real life. Any feature that connects people needs clear expectations, no pressure to participate, and no incentives to overshare location or personal details.
- **Leave no trace, digitally too.** Keep it small, pack it out, don't leave a mark. A feature we're unsure the community actually wants is a feature we leave out.

The goal isn't a "trail magic" feature. It's an app that acts like a good trail angel: generous, attentive, low-impact, and quick to get out of the way once it's helped.

---

*This document is a living draft — expect it to be revised as the project takes shape and as more voices (NYNJTC leadership, volunteers, potential ATC club partners) weigh in.*
