"""NJDEP / NJGIN — Statewide Trails: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch b5_nyc_nj_ct_ma_pa).

These are short descriptions, not itineraries.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The hosted trails layer\'s `trail_desc` has real text on 1,519 of 3,068 segments ("Unknown" on the '
        'rest), for example Wawayanda Lake Loop Trail, "Great lake view". The on-prem copy that is loaded has '
        "no description field. `https://dep.nj.gov/parksandforests/first-day-hikes/` exists per the search "
        "index, but the site is walled.",
    ),
    where=(
        "https://dep.nj.gov/parksandforests/first-day-hikes/",
        "https://mapsdep.nj.gov/arcgis/rest/services",
        "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
