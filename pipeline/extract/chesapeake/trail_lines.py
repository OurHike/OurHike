"""Chesapeake Conservancy: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

A water trail. Baywide_Trails has unknown provenance and could duplicate state layers

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own: `https://cicgis.org/arcgis/rest/services/Chesapeake/CAJO/MapServer/0` "CAJO_Complete": 843 lines,'
        ' `copyrightText` "Chesapeake Conservancy". `cicgis.org/…/Baywide_Trails/MapServer/0`: 23,146 lines (a '
        "compilation; `source` fields blank on samples). Upstream: "
        "`NPSAGOL/CAJO_Captain_John_Smith_Chesapeake_NHT_Centerline_ln/0`: 832 lines (2026-05-14). "
        "`nps_trails`: 0",
    ),
    where=("https://cicgis.org/arcgis/rest/services/Chesapeake/CAJO/MapServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
