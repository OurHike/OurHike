"""NYC Department of Transportation: closures, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

(a) is the find for NYC. It names long-term closures of tread `nyc_dot_greenways` draws today, and
East River Park is the largest. It is a page of 8 links, cheap to scrape and cheap to diff. (b) is
roadway work, joinable by `segmentid` to `nyc_cscl_paths`/`nyc_park_drives` if a drive is ever …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "(a) Greenway Closures on `https://www.nyc.gov/html/dot/html/bicyclists/greenways.shtml` (page, 200). "
        'It lists 8 closures "lasting more than three months", posted under Local Law 115 of 2022: Brooklyn 1 '
        "(Red Hook), Manhattan 6 (South Street Dover–Catherine Slip for the BMCR project; East River Park, "
        "Montgomery St to E 15th St, for ESCR; the Battery to the BPC esplanade; E 114th–117th St; the 79th "
        "Street Rotunda; the East River Esplanade at E 70th–75th St), and Staten Island 1 (the North Shore "
        "Esplanade). Each links to the managing agency's own notice. (b) …",
    ),
    where=("https://www.nyc.gov/html/dot/html/bicyclists/greenways.shtml",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
