"""Catamount Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A page, and a NOTE paragraph rather than a structured field. One live hazard banner across 33
sections. Low volume, but it is the club's own hazard notice, which is what this mart holds.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://catamounttrail.org/wp-json/wp/v2/pages?slug=section-31-jay-pass-to-canadian-border
(wordpress); https://www.fs.usda.gov/r09/gmfl/alerts (html_page).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://anrmaps.vermont.gov/arcgis/rest/services/map_services/MAP_ANR_ANRATLASFPR_WM_NOCACHE/MapServer/3,
Vermont ANR's trail layer: 1,625 trails, every Status 'EX', so it carries no closure (a trail_lines
layer for decision 54's first wave).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://catamounttrail.org/ski-the-trail/ct-section-list/section-31-jay-pass-to-canadian-border/` "
        'opens with "NOTE: There is logging actively taking place on Section 31 south of the Jay Country Store.'
        " If you encounter active logging please keep your distance…\" (page modified 2025-09-17). Section 6's "
        'page reads "Be alert for temporary detours due to scheduled logging." Plus the static "Safety On The '
        'Trail" and "Safety In The Backcountry" pages and one ad hoc post, "Warning: Increased Avalanche Danger'
        ' In New England Backcountry".',
    ),
    where=("https://catamounttrail.org/ski-the-trail/ct-section-list/section-31-jay-pass-to-canadian-border/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
