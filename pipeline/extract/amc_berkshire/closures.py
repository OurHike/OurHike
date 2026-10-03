"""AMC Berkshire Chapter: closures, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's closures arrive through _shared/ma_dcr/ `ma_dcr_park_alerts`, each extracted once in its
steward's folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.amc-wma.org/documents-more.cgi?id=112 (html_page);
https://www.amc-wma.org/documents-more.cgi?id=13 (html_page).

Before decision 53 phase B, 2026-10-03, this note read:

AMC Berkshire Chapter: closures, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Weak and seasonal. These are access closures and one facility closure; none obstructs the footpath,
so under decision 7 they land as warnings, or as season attributes on the POI rows (Reasoned). They
matter for getting off the trail quickly: in winter the Greylock road crossings are not exits. …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via _shared/ma_dcr/ `ma_dcr_park_alerts` (decision 53 phase B, 2026-10-03): `ma_dcr_park_alerts` reads `FACILITYCLOSURE_APPDATA/FeatureServer/0`",
        'There are no dated notices. Standing seasonal closures appear on two pages. (1) `documents-more.cgi?id=13`: "Upper Goose Pond Cabin is open with a volunteer caretaker … from mid-May to mid-October. Cabin is closed when no caretaker is present." (2) `https://www.amc-wma.org/documents-more.cgi?id=112` "A.T. Parking Areas and Trailhead" (A.T. Management Committee, 11-Jan-2025): "Notch Rd is not open in winter (Nov to May)"; the Mt Greylock summit is "closed in winter (late Oct to late May)"; Gould Trail and "Hairpin Turn" parking are "Closed in winter (late October to late May)"; at Mt Everett …',
    ),
    where=(
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/FACILITYCLOSURE_APPDATA/FeatureServer/0",
        "https://www.amc-wma.org/documents-more.cgi?id=112",
    ),
    reason="drawn from _shared/ma_dcr/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
