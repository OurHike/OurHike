"""Oregon Natural Desert Association: challenges, a completion award with no list of places, and not landed (decision
54 wave 5, section K, 2026-10-04).

The Badlands Challenge (2019): hike the Badlands Wilderness trails (more than 50 miles), then e-mail a trip log.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Oregon Natural Desert Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Page. Skeptic: the page (created 2019-03-15, modified 2022-12-02) still reads as open: "There are 50+
miles of trails in Badlands. Can you hit them all?". But the post `/we-challenged-you-hiked/` calls it
"a six-month-long exploration challenge" for the wilderness's tenth anniversary. Whether it …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/badlands-challenge/` (2019): hike the Badlands Wilderness trails
(more than 50 mi), then email a trip log.

Its `where`: https://onda.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /badlands-challenge/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://onda.org/badlands-challenge/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
