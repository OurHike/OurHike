# OurHike

Hike your own hike & connect with communities that maintain our trails

An offline-first map for the Appalachian Trail — topo background, water sources, shelters, campsites and resupply, elevation profiles, and a way to report what you find out there back to the people who maintain it. Built as a PWA, wrapped for iOS and Android, and designed from the start to be handed to another club rather than owned by whoever wrote it.

**Status:** launched — v1.0.0 ("Springer Mountain") shipped 2026-08-16: the data is published to the public bucket, the app is live at [ourhike.org](https://ourhike.org), and [releases/v1.0.0-springer-mountain.md](releases/v1.0.0-springer-mountain.md) is the record. Not yet real: the backend is not hosted anywhere (#600), real OAuth has never been exercised end to end (#92), and the migration has never been applied to Supabase's Postgres. Contributing paths therefore wait on ops work, while the map itself is live.

## Where to start

| | |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to report something, run the code, and open a pull request |
| [Issues](https://github.com/OurHike/OurHike/issues) | Open work — [`good first issue`](https://github.com/OurHike/OurHike/labels/good%20first%20issue) if you want somewhere to begin |
| [OurHikeValues.md](OurHikeValues.md) | The nine values every design decision here is argued against |
| [FEATURES.md](FEATURES.md) | What the product is |
| [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) | How it is built, and why those choices |
| [ROADMAP.md](ROADMAP.md) | The phases and where things stand |
| [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) | The ordered runbook for deploying v1 |

Found a blowdown or a washed-out crossing? That goes through the app's own "Report a problem" flow, not this repository — it reaches a moderator who can act on it.

## Licence

AGPL-3.0. The data it ships is not all ours to relicense — see [CONTRIBUTING.md](CONTRIBUTING.md#a-note-on-data-and-licences).
