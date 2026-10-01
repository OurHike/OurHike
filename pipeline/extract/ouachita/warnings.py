"""Friends of the Ouachita Trail: warnings, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Machine-readable, but read the xlsx, not the CSV, or the one field that says "treacherous" is lost.
Drop the two name columns. The `Last-Modified` headers on FoOT's PDFs all read 2026-09 and do not
match the files' own dates, so do not use them for freshness.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Trail Condition Report, Google Sheet `1_3_u_8gtQSoiFSgzVAf3uGwPMj_nqQ25`, gid `866760807`. CSV export "
        '`…/export?format=csv&gid=866760807` (22,955 bytes). Header date "9/20/2026". 190 segment rows by begin'
        " and end mile marker, with the last report month (most often 10/25 or 10/24) and 36 comments, e.g. "
        '"Large Oak Tree down at 74.8 at least 2ft diameter", "Fiddler Shelter needs a tarp and shovel". Hiker '
        "Alert PDF `/wp-content/uploads/2026/01/Hiker-Alert-OT-MM-195.pdf`: logging at MM 194–195, with blue "
        'streamside markings that "could be confusing to hikers".',
        "Skeptic corrections (Measured …",
    ),
    where=("https://friendsoftheouachita.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
