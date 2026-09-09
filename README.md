# OurHike

Hike your own hike & connect with communities that maintain our trails

An offline-first map for hikers — inspired by the Appalachian Trail, and drawn from the published data of five trail organizations. Topo background, water sources, shelters, campsites and resupply, elevation profiles, and a way to report what you find out there back to the people who maintain it. Built as a PWA, wrapped for iOS and Android, and designed from the start to be handed to another club rather than owned by whoever wrote it.

**Which organizations, and on what terms**, is not a thing this file should keep a second copy of: the app's own **Where this map comes from** screen names them on the phone, [ourhike.org/about](https://ourhike.org/about/) names them on the web, and [pipeline/sources.json](pipeline/sources.json) is the registry both of those read from. It currently holds 33 registered sources across nine organizations, five of which publish the trail lines the map draws.

**Status:** launched — v1.0.0 ("Springer Mountain") shipped 2026-08-16: the data is published to the public bucket, the app is live at [ourhike.org](https://ourhike.org), and [releases/v1.0.0-springer-mountain.md](releases/v1.0.0-springer-mountain.md) is the record. Not yet real: the backend is not hosted anywhere (#600), and Apple sign-in has never been exercised end to end — Google's half verified live against the real project (#92). The migration is applied to both real Supabase projects (#95); production trails UA by a few revisions pending a deliberate `migrate.yml` dispatch, the normal BEHIND state rather than a gap. Contributing paths therefore wait on #600, while the map itself is live.

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
