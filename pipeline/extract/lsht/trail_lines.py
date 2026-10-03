"""Lone Star Hiking Trail Club: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c8_regional_5).

The S3 links expire, so a loader must resolve `docs.ashx` each run. Skeptic: `docs.ashx?id=1401145`
resolved on 2026-10-01 to
`s3.amazonaws.com/ClubExpressClubFiles/738078/documents/LSHT_All_Tracks_35787600.gpx`, but only with
a session cookie and a browser User-Agent. Without them it returns 403 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Via `usfs` → `usfs_trails`: `LONE STAR` 081304 (Sam Houston NF), 5 features / 96.96 mi. A sixth match,"
        " `LONE STAR` 051354, is a 0.10-mi motorized California trail and a false hit. Own geometry (AVAILABLE,"
        ' not loaded): "LSHT System All Tracks" and "LSHT Main Trail - Track" GPX (`/docs.ashx?id=1401145`, '
        "`id=1401144`, which redirect to signed S3 URLs under `ClubExpressClubFiles/738078/documents/`); two "
        '"EFSJR Bypass" GPX (`id=1401257`, `id=1401291`); KML item `fe8e5d8c77544b27be1da87ab809779f` (194,156 '
        "B, 2024-06-19).",
    ),
    where=("https://s3.amazonaws.com/ClubExpressClubFiles/738078/documents/LSHT_All_Tracks_35787600.gpx",),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
