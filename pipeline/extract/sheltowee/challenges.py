"""Sheltowee Trace Association: challenges, a completion award with no list of places, and not landed (decision 54 wave
5, section K, 2026-10-04).

The Hiker Challenge ('343 Miles. 11 Months.', a schedule of dated group sections) and the E2E Registry (a
certificate, patch, rocker and mileage decal).

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Sheltowee Trace Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

The programme only. The registry PDFs and XLSX are names.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Hiker Challenge (`/hiker-challenge`): "343 Miles. 11 Months.",
"Over 650 participants have completed the Challenge". E2E Registry: certificate, patch, rocker and
mileage decal (`/e2e-awards-and-recognition`).

Its `where`: https://apps.fs.usda.gov/arcx/rest/services https://sheltoweetrace.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /hiker-challenge and /e2e-awards-and-recognition",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://sheltoweetrace.org/hiker-challenge",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
