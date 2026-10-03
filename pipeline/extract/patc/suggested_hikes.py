"""Potomac Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

The Avenza hikes fall under the Council term and point at paid maps, the same issue as the `avenza`
refuse row. The section guides are the club's own free prose.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Hikes_Sort/0`: 40 hike footprints (Name, Length_mi, ElevGn_ft, Difficulty, Link → `link.avenza.com`, "
        "the paid maps), 2021-09-24. hikethetuscarora.org: 22 section guides (distance, PATC map, elevations, "
        "access coordinates, camping). The guidebooks (Circuit Hikes 11th ed., Hikes in the Washington Region "
        "Part B 6th ed. 2025, A.T. guides) are sold and not loadable",
    ),
    where=(
        "https://link.avenza.com",
        "https://hikethetuscarora.org",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
