"""Potomac Appalachian Trail Club: closures, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

~~(b) bites as soon as any Tuscarora line reaches a hiker.~~ Skeptic, 2026-10-01: (b) bites now.
`usfs_trails` (`EDW_TrailNFSPublish_01/MapServer/0`, sources.json `reaches_hikers: true`) has
`trail_name = 'TUSCARORA - DOLL RIDGE'`, 3.7 mi, `admin_org` 080804 (Measured).
`export_nearby_trails.py` …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '(a) `https://www.patc.net/trails` banner: "Byron Bridge Update… Stairway access to the C&O Canal '
        'Towpath will be closed… starting Monday, July 27, 2026", with an NPS shuttle (HTML). (b) '
        '`https://www.hikethetuscarora.org/updates`: the "Doll Ridge section from Three Top Mountain to '
        'Riverview Drive" of the Tuscarora is "closed due to loss of landowner permission", with a road detour '
        "of about 7 mi and turn-by-turn directions (HTML). There is no feed for either: `/feed/rss2` is the "
        "newsletter, and none of the 58 services is a closures layer. The A.T. closures in PATC's section are "
        "LOADED via atc …",
    ),
    where=(
        "https://www.patc.net/trails",
        "https://www.hikethetuscarora.org/updates",
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_TrailNFSPublish_01/MapServer/0",
        "https://patc.net/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
