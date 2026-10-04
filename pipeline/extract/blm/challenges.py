"""Bureau of Land Management: challenges, National Historic Trail passport stamps at visitor centres and
museums, and not landed (decision 54 wave 5, section K, 2026-10-04).

The New Mexico page lists where the stamps are kept: Aztec Ruins National Monument, the Kit Carson Home and Museum,
the New Mexico Public Lands Info Center and the like, visitor centres and museums along three historic trails, not
places on a trail a hiker walks to. The Iditarod NHT passport is iditarod/'s.

The note this replaces read, whole:

Bureau of Land Management: challenges, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Page only. The stamp sites would need geocoding.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01):
`https://www.blm.gov/programs/recreation/recreation-activities/new-mexico/commemorative-anniversary-stamps`:
"Passport Stamps now available for New Mexico and West Texas National Historic Trails", with a "Where
Can I get my passport stamps?" section. Iditarod NHT passport (c11).

Its `where`:
https://www.blm.gov/programs/recreation/recreation-activities/new-mexico/commemorative-anniversary-stamps

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.blm.gov/programs/recreation/recreation-activities/new-mexico/commemorative-anniversary-stamps (HTTP 200, 82,296 bytes, 2026-10-04): 'Where Can I get my passport stamps?', visitor centres and museums",
    ),
    where=("https://www.blm.gov/programs/recreation/recreation-activities/new-mexico/commemorative-anniversary-stamps",),
    reason="not this type: a stamp passport kept at visitor centres and museums, not places on trails",
)
