"""Hoosier Hikers Council: warnings, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

One notice. The Knobstone "streams unpredictably dry" line is a water note, so it stays out of
warnings by poll 2. (Skeptic, 2026-10-01: re-read, and the SR 45 text is unchanged. Upstream, IN
DNR's Knobstone callout has a "Knobstone Trail advisories" list: "Be prepared for wetter trail
conditions …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('The Tecumseh page warns of a 1-mile road walk on SR 45, a "busy highway with little to no shoulder". HTML prose.',),
    where=(
        "https://gisdata.in.gov/server/rest/services",
        "https://hoosierhikerscouncil.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
