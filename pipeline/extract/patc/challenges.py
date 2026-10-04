"""Potomac Appalachian Trail Club: challenges, the Tuscarora patch and the Centennial Team Hiking Challenge,
and not landed (decision 54 wave 5, section K, 2026-10-04).

The Tuscarora Trail patch and rockers (thru or section, a rocker per state, '250 Miler') are a completion award; the
1200 Mile Centennial Team Hiking Challenge (2026-06-01 to 2027-12-31) lists its eligible trails in an Airtable
shared view, a third party's application this pipeline does not read. No request sent today.

The note this replaces read, whole:

Potomac Appalachian Trail Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

(1) is a lasting end-to-end programme. (2) is time-boxed, and I did not test whether its Airtable view
exports. The volunteer awards (Hawksbill, Myron Avery) are service awards.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): (1) Tuscarora Trail patch and rockers (thru or section, a rocker
per state, a "250 Miler" rocker; email the itinerary to an email address; offered with REI):
`https://www.hikethetuscarora.org/hike-the-tuscarora` (page). (2) 1200 Mile Centennial Team Hiking
Challenge, 2026-06-01 → 2027-12-31; eligible trails are listed in an Airtable shared view,
`https://airtable.com/appwOOb1m00ZTcHxT/shrB0s3bUs7yEVmWF/tbl4jf0v79ulnAtCh`
(`/patc-centennial-kickoff-hiking-challenge`)

Its `where`: https://www.hikethetuscarora.org/hike-the-tuscarora
https://airtable.com/appwOOb1m00ZTcHxT/shrB0s3bUs7yEVmWF/tbl4jf0v79ulnAtCh

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /hike-the-tuscarora and the Airtable view shrB0s3bUs7yEVmWF",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://www.hikethetuscarora.org/hike-the-tuscarora",),
    reason="not this type: a completion award, and a list held in Airtable, which is not read",
)
