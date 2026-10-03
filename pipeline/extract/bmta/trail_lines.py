"""Benton MacKaye Trail Association: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c8_regional_5).

About 106 of 287.6 mi. The Smokies section is NPS ground and its trail names differ, so it is
unaccounted for here.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Via `usfs` → `usfs_trails`: 14 TERRA features, all `terra_motorized='N'`, 106.09 mi. By segment: "
        "`BENTON MACKAYE` 080302, 4 / 54.48 mi; 080407, 3 / 20.63 mi; `BENTON MACKAYE -CHEOAH RD` 081102, 6 / "
        "30.98 mi; `… - TUSQUITEE RD` 081109, 1 / null miles. Own geometry: none published. The site links "
        "onX/REI Hiking Project (`hikingproject.com/trail/7064109/benton-mackaye-trail`) and FarOut (paid).",
    ),
    where=("https://hikingproject.com/trail/7064109/benton-mackaye-trail",),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
