"""Friends of the Ouachita Trail: warnings, from FoOT's Trail Condition Report sheet and its Hiker Alert PDF,
hourly (decision 53, phase B).

`foot_trail_condition_report` reads the Google Sheet's CSV export, one row per trail segment: 184 on
2026-10-03, in four tables (the Ouachita Trail, Black Fork Wilderness, Eagle Rock Loop, the Womble
Trail), each with its begin and end mile, the month of its last condition report and the comment,
such as "Down tree removed". The two columns that name people, "Adopted by" and "Source of Last
Condition Report", never load: the reader keeps an allow list (extract/_json_apis.py's
SHEET_COLUMNS).

WHAT DOES NOT LAND. The sheet's condition is the colour of each segment's cells (its legend: green
clear, yellow some impediment, red difficult to follow, gray no current report, plus blue and
orange), and a CSV export carries values, not colours. The coverage audit said so first: "read the
xlsx, not the CSV, or the one field that says 'treacherous' is lost". The xlsx needs a spreadsheet
reader the extract job does not install; that is the maintainer's call, and until it is made the
segment a hiker most needs to hear about is the one this table cannot mark.

`foot_hiker_alert_mm195` is FoOT's other channel, the Hiker Alert PDF
(`/wp-content/uploads/2026/01/Hiker-Alert-OT-MM-195.pdf`: logging at MM 194–195, with blue streamside
markings that "could be confusing to hikers"), read as one PageNotice over the PDF
(extract/_notices.py): the registry's title, the PDF's own ModDate (2026-01-08) and the bytes' sha256,
no text. The `Last-Modified` headers on FoOT's PDFs all read 2026-09 and do not match the files' own
dates (coverage audit, 2026-10-01), so they are never its date. friendsoftheouachita.org's robots.txt
asks `Crawl-delay: 10` (read 2026-10-03 under our agent), which the reader keeps; the file's strong
ETag ("6aab4827-47257") is a static file's, so a conditional GET answers 304 between edits
(`trust_validators`; @unvalidated, one read). The URL is one alert's: the next alert arrives at a new
upload path, which a person registers.
"""

from extract._json_apis import sheet_csv_segments
from extract._kinds import page_notice

CLAIMS = ("foot_trail_condition_report", "foot_hiker_alert_mm195")
RESOURCES = [
    sheet_csv_segments("foot_trail_condition_report"),
    page_notice("foot_hiker_alert_mm195", crawl_delay=10, trust_validators=True),
]
