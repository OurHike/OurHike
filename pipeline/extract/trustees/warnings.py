"""The Trustees of Reservations: warnings, from the hunting page and the hunting-designations PDF, hourly
(decision 53 phase B, 2026-10-03).

Both read live under our agent on 2026-10-03 after thetrustees.org's robots.txt (Yoast, nothing
disallowed), each as one PageNotice (extract/_notices.py) that lands a title, a date, a hash and the
link, and no text:

- `trustees_hunting`: https://thetrustees.org/content/hunting-on-trustees-properties/, a 'content'
  post the site's REST API does not expose, read as HTML. "Roughly half of our properties allow some
  form of hunting", in three designations; dated by its JSON-LD dateModified, 2026-09-16. The page
  has no <main> or <article>, so the region is <body>.
- `trustees_hunting_designations`: the per-property PDF
  (/wp-content/uploads/2025/10/TrusteesPropertyHuntingDesignations_Oct2025.pdf, 48,295 bytes), dated by
  its own ModDate, 2025-10-16. Its strong ETag ("6998c8b4-bca7") is a static file's, so a conditional
  GET answers 304 between edits (`trust_validators`; @unvalidated, one read). Its three columns of
  property names are a place attribute that joins to the `Trustees_props` polygons, not notices. The
  upload path is dated (2025/10): next season's list will arrive at a new URL, found from the page.

Standing seasonal warnings both. Each place page's 'Regulations & Advisories' (Notchview's "Hunting is
permitted at this property north of Bates Rd and south of Route 9 only") is a later per-page reader.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c4_regional_1), which found both and why the original survey missed them: the site's `place`,
`content` and `program` post types are not registered in its REST API.
"""

from extract._kinds import page_notice

CLAIMS = ("trustees_hunting", "trustees_hunting_designations")
RESOURCES = [page_notice("trustees_hunting"), page_notice("trustees_hunting_designations", trust_validators=True)]
