"""Keystone Trails Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c1_at_clubs_north).

The Laurel Highlands shelter areas are a DCNR facility, so dedupe against `pasda_dcnr_trails` and
any DCNR POI row.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "LOADED via atc (code 11): shelter 1 (George W. Outerbridge), parking 3, viewpoints 18. Not loaded: "
        "CalTopo markers, which are trailhead parking (e.g. 11 parking markers on the Quehanna map).",
        "Skeptic, 2026-10-01, all 6 maps: 52 markers (Quehanna 12, Allegheny Front 10, Thunder Swamp 5, Pinchot"
        " 5, Conestoga 0, Laurel Highlands 20). They are almost all parking. The Laurel Highlands map adds "
        'shelter-area trail junctions ("Ohiopyle Shelter trail jct", "Grindle Ridge Shelter trail jct", '
        '"Turnpike Shelter trail jct" …), and Thunder Swamp and Pinchot add "Stone Dam Crossing" and "Choke '
        'Creek Falls".',
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://kta-hike.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
