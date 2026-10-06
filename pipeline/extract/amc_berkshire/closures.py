"""AMC Berkshire Chapter: closures, 2 notice sources read here (decision 53 phase B, 2026-10-03).

- `amc_wma_at_parking`: AMC Berkshire Chapter: A.T. Parking Areas and Trailheads, one notice for the
  page (PageNotice). Standing seasonal access closures at the Massachusetts A.T.'s trailheads
  ("Summit is closed in winter (late Oct to late May)"), dated 11-Jan-2025 in its own text.

- `amc_wma_at_campsites`: AMC Berkshire Chapter: Campsites and Shelters on the Massachusetts A.T.,
  one notice for the page (PageNotice). Standing facility notes for the chapter's campsites and
  shelters (Upper Goose Pond Cabin 'closed when no caretaker is present'), dated 04-Jan-2025 in its
  own text.

Also drawn from _shared/ma_dcr/'s `ma_dcr_park_alerts` (DCR's FACILITYCLOSURE_APPDATA layer),
extracted once there (decision 34); which DCR PARK_SITE values lie on the Massachusetts A.T. is
still unchecked.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

AMC Berkshire Chapter: closures, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's closures arrive through _shared/ma_dcr/ `ma_dcr_park_alerts`, each extracted once in its
steward's folder (decision 34). Its portion is assigned in dbt.

Before decision 53 phase B, 2026-10-03, this note read:

AMC Berkshire Chapter: closures, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Weak and seasonal. These are access closures and one facility closure; none obstructs the footpath,
so under decision 7 they land as warnings, or as season attributes on the POI rows (Reasoned). They
matter for getting off the trail quickly: in winter the Greylock road crossings are not exits. …

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-03): via _shared/ma_dcr/ `ma_dcr_park_alerts` (decision 53 phase B,
2026-10-03): `ma_dcr_park_alerts` reads `FACILITYCLOSURE_APPDATA/FeatureServer/0` | There are no
dated notices. Standing seasonal closures appear on two pages. (1) `documents-more.cgi?id=13`:
"Upper Goose Pond Cabin is open with a volunteer caretaker … from mid-May to mid-October. Cabin is
closed when no caretaker is present." (2) `https://www.amc-wma.org/documents-more.cgi?id=112` "A.T.
Parking Areas and Trailhead" (A.T. Management Committee, 11-Jan-2025): "Notch Rd is not open in
winter (Nov to May)"; the Mt Greylock summit is "closed in winter (late Oct to late May)"; Gould
Trail and "Hairpin Turn" parking are "Closed in winter (late October to late May)"; at Mt Everett …

Its `where`:
https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/FACILITYCLOSURE_APPDATA/FeatureServer/0
https://www.amc-wma.org/documents-more.cgi?id=112

Its `reason`: drawn from _shared/ma_dcr/'s resources, extracted once there (decision 34); checked
names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the
docstring, still to wire
"""

from extract._kinds import page_notice

CLAIMS = ("amc_wma_at_parking", "amc_wma_at_campsites")
RESOURCES = [page_notice("amc_wma_at_parking"), page_notice("amc_wma_at_campsites")]
