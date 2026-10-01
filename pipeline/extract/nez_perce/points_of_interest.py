"""Nez Perce (Nee-Me-Poo) Trail Foundation: points of interest, published, and not landed (coverage
audit 2026-10-01, batch p02_persist).

Licence: the KML carries no licence text; the words copyright and licence do not occur in it. It is
USFS and NPS work, so open_licence, public domain as a federal work (Reasoned, 17 U.S.C. 105). It is
hosted on Google My Maps, which the audit left as a maintainer question. `tnpt` interpretive …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "USFS My Maps KML `https://www.google.com/maps/d/kml?mid=1rdJCOzX2Wh3yt7E-nVDfrz0CbSc&forcekml=1` "
        '(1,184,784 B; fetched once and deleted). Document "Nez Perce National Historic Trail": 135 placemarks.'
        ' Folder "Auto Tour Stops": 110 points. "Suggested Travel Routes": 12 placemarks, 15 LineStrings. '
        '"Adventure Routes": 13 placemarks, 15 LineStrings. Its description credits an NPS mapmaker by name '
        "(not copied). Interpretive signs: "
        "`https://services1.arcgis.com/CPCzfCPkoQSKO5TC/arcgis/rest/services/NPNHT_Interpretive_Points/FeatureServer/1`"
        ' has 265 points. Its snippet reads "Existing interpretive …',
    ),
    where=(
        "https://www.google.com/maps/d/kml?mid=1rdJCOzX2Wh3yt7E-nVDfrz0CbSc&forcekml=1",
        "https://services1.arcgis.com/CPCzfCPkoQSKO5TC/arcgis/rest/services/NPNHT_Interpretive_Points/FeatureServer/1",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services",
        "https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services",
        "https://nezpercetrail.net/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
