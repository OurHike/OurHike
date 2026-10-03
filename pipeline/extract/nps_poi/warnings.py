"""National Park Service: warnings, drawn from nps/warnings.py's NPS alerts resource (decision 53,
phase B, 2026-10-03).

NPS's alerts land once, in nps/warnings.py's `nps_alerts`, for the park codes sources.json's entry
lists in `park_codes`, which are the codes club folders draw on. This folder's points are in every
NPS unit, and the units no club names are not read (622 alerts nationwide on 2026-10-03), so most of
this layer's parks get no NPS alert from there: the maintainer's call. NPS's Danger, Caution and
Information categories are the warnings half, split from the rest in dbt.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

That Danger example is a closure filed under Danger. The category is not a reliable closure/warning
split on its own.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, the national list (the decision 53 inventory, batch 5, 2026-10-03): 622 alerts. "
            "nps/warnings.py's nps_alerts lands only the park codes club folders name, not this list."
        ),
        (
            "(coverage audit, 2026-10-01) Same endpoint: the `Danger` and `Caution` categories (23 of 100 "
            'sampled). Example: "South Pasture Trail, all River Access Closed Due to Flood Conditions" (Danger).'
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts",
        "https://nps.gov/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
