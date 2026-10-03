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

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Benton MacKaye Trail Association: closures, drawn from nps/warnings.py's NPS alerts resource
(decision 53, phase B, 2026-10-03).

NPS's alerts for park code `grsm` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's `Park Closure` category is
the closures half, split from the rest in dbt; a Park Closure most often closes a facility or a road
rather than a trail, and no alert carries geometry, so it never sets `obstructs_trail` alone.

The inventory also found a PDF, a web page for this club, which other phase B readers take; if one
lands for this type it takes this file, and this note becomes a line in its docstring.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

PDF. Also `bmtamail.org/docs/KnowBeforeYouGo.pdf`.

Its `checked` (confirmed 2026-10-03): NPS alerts API, `parkCode=grsm` (the decision 53 inventory,
batch 3, 2026-10-03): 3 (Park Closure 'Park Headquarters Road is closed' 2026-06-26; Park Closure
'Straight Fork ... Balsam Mountain Road closed' 2025-11-12; Information 'Most visitors need a
parking tag'). Tiebreak for the GSMNP fire-ban disagreement. Landed by nps/warnings.py as
nps_alerts. | (coverage audit, 2026-10-01) "Current Alerts & Advisories",
`https://bmtamail.org/docs/CurrentAlertsandAdvisories.pdf`: a 1-page PDF, Last-Modified 2026-09-09,
289,535 B. It held 0 closure items today, but it is the channel the BMTA posts to.

Its `where`: https://developer.nps.gov/api/v1/alerts?parkCode=grsm
https://bmtamail.org/docs/CurrentAlertsandAdvisories.pdf
https://bmtamail.org/docs/KnowBeforeYouGo.pdf

Its `reason`: drawn from nps/'s resources, extracted once there (decision 34); checked names the
layer this org's data arrives in
"""

from extract._kinds import page_notice

CLAIMS = ("bmta_alerts_pdf",)
RESOURCES = [page_notice("bmta_alerts_pdf", trust_validators=True)]
