"""Appalachian Mountain Club (A.T. sections): warnings, drawn from amc/'s `amc_facility_conditions`
(decision 53 phase B, 2026-10-03).

The huts' and lodges' status and conditions page
(https://www.outdoors.org/weather-trail-conditions/) is AMC's own, read once in amc/closures.py as
`amc_facility_conditions` (decision 34); this folder's portion is assigned in dbt. On 2026-10-03 its
16 facility blocks all read 'Status: Open', and its daily notes were dated 05/30/26 and 05/29/26,
four months old, so a date is read per facility, never from the page. The NH A.T. trail closures ATC
carries stay with `atc_trail_updates`.

Before decision 53 phase B, 2026-10-03, this note read:

Appalachian Mountain Club (A.T. sections): warnings, published, and not landed (coverage audit
2026-10-01, batch c1_at_clubs_north).

The Pemi rule is also LOADED via atc ("New Hampshire: Bear Can Requirement in the Pemi Wilderness",
not placed on the map). The daily note was 4 months stale when read, so freshness has to be checked
per field.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The same conditions page. Its daily note for the Highland
Center (dated 05/30/26 when read) gave temperature, "Wet trails, watch out for river crossings" and
snow and ice above 3,000 ft. The `backcountry-campsites` record states the Pemigewasset
bear-canister rule effective 2026-05-01. There is also a news post
`/resources/amc-outdoors/news/bear-canisters-required-pemigewasett/`.

Its `where`: https://outdoors.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via amc/ `amc_facility_conditions` (decision 53 phase B, 2026-10-03): PageNotice over https://www.outdoors.org/weather-trail-conditions/",
        "(the decision 53 inventory, batch 5, 2026-10-03) 16 facility blocks, all 'Status: Open'; notes dated 05/30/26 (Highland Center) and 05/29/26 (Joe Dodge Lodge); JSON-LD dateModified 2026-02-18.",
    ),
    where=("https://www.outdoors.org/weather-trail-conditions/",),
    reason="drawn from amc/'s resources, extracted once there (decision 34); checked names the resource this org's data arrives in",
)
