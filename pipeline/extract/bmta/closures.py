"""Benton MacKaye Trail Association: closures, 1 notice source read here (decision 53 phase B,
2026-10-03).

- `bmta_alerts_pdf`: BMTA Current Alerts & Advisories, one notice for the document (PageNotice over
  a PDF). The club's one-page Current Alerts & Advisories PDF, one notice a document. Its strong
  ETag and a Last-Modified older than the request are a static file's, so a conditional GET's 304 is
  FRESH. The PDF carries two staff e-mail addresses; the reader lands only its title, its stated
  date, its byte count and a sha256 of the bytes, so none of its text reaches the raw store.

The site alert bar (warnings.py) disagreed with this PDF on 2026-10-03: the bar says a park-wide
fire ban is in effect in the Great Smoky Mountains, the PDF calls it 'Cancelled', and NPS's GRSM
alerts carry none. NPS's alerts for grsm land once in nps/ (decision 34).

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

CLAIMS = ("bmta_alerts_pdf",)
RESOURCES = [page_notice("bmta_alerts_pdf", trust_validators=True)]
