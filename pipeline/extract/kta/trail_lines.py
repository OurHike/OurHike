"""Keystone Trails Association: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c1_at_clubs_north).

CalTopo is a third-party platform, and nobody has read its terms (@unvalidated). The Laurel
Highlands is already in `pasda_dcnr_trails` (3 features per `trail_orgs.json`). Nobody has checked
the others against PASDA (@unvalidated). Skeptic, 2026-10-01: all 6 map JSONs read (2,260,334 bytes
in …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "6 CalTopo maps on `https://www.kta-hike.org/maps.html`: Allegheny Front, Conestoga, Laurel Highlands, "
        'Pinchot, Quehanna, Thunder Swamp. Each says "GPS data collected and verified by KTA" between Spring '
        "2023 and Winter 2026. Map IDs: 28V9AS6, DUMMFCS, FEH1A8K, FN5E27S, L06QRV6, PNC0GEQ. Public JSON at "
        "`https://caltopo.com/api/v1/map/<id>/since/0`. Sample 28V9AS6 (Quehanna) holds 6 LineStrings and 12 "
        'Markers. The A.T. section is LOADED via `atc` (polygon "Keystone Trails Association").',
    ),
    where=(
        "https://www.kta-hike.org/maps.html",
        "https://caltopo.com/api/v1/map/",
        "https://kta-hike.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
