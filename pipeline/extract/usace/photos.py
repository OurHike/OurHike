"""US Army Corps of Engineers: photos, could not be told (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Still UNKNOWN. DVIDS military imagery is usually public domain, but nobody read DVIDS's terms today.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "RIDB `/media` sits behind the key; usace.army.mil/Media/Images (DVIDS) was not opened.",
        "Skeptic: `usace.army.mil/Media/Images/` answers 403 even to a browser user agent. The DVIDS API "
        'answers `"Bad Request - No API key was provided"`. The Corps Lakes Gateway has per-lake photo albums '
        "(`corpslakes.erdc.dren.mil/visitors/album.cfm?Option=View&Id=<project>`, HTTP 200; Crooked Creek "
        "Lake's album page has 12 `<img>` tags, some of them site chrome) with no licence or credit text.",
    ),
    where=("https://usace.army.mil/",),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
