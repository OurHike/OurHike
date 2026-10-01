"""USDA Forest Service: podcasts, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Forest Focus includes a trail-crew episode ("Trails in Transformation", search). "Forest North" is
the Ely Tourism Bureau's show, not USFS's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Forest Focus (USDA Forest Service, Pacific Southwest Region): "
        "`https://rss.libsyn.com/shows/433686/destinations/3617892.xml`, 38 episodes, newest 2024-12-21. "
        "Forestcast (research): `https://rss.libsyn.com/shows/184682/destinations/1267985.xml`, 36 episodes, "
        'newest 2024-12-18. Custer Gallatin "Forest in Focus" '
        "(`fs.usda.gov/r01/custergallatin/multimedia/audio`, search).",
    ),
    where=(
        "https://rss.libsyn.com/shows/433686/destinations/3617892.xml",
        "https://rss.libsyn.com/shows/184682/destinations/1267985.xml",
        "https://fs.usda.gov/r01/custergallatin/multimedia/audio",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
