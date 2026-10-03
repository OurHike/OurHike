"""Benton MacKaye Trail Association: warnings, 1 notice source read here (decision 53 phase B,
2026-10-03).

- `bmta_alert_bar`: BMTA site alert bar, one notice for the page (PageNotice, region
  `.alert-bar__content`). The site-wide alert bar on bmta.org's home page, read alone
  (`div.alert-bar__content`). bmta.org asks `Crawl-delay: 60`, one request an hour at most. The bar
  disagreed with the PDF on 2026-10-03 (a GSMNP park-wide fire ban the PDF calls 'Cancelled' and
  NPS's alerts do not carry), so neither publishes as current without NPS's alerts beside it.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Benton MacKaye Trail Association: warnings, drawn from nps/warnings.py's NPS alerts resource
(decision 53, phase B, 2026-10-03).

NPS's alerts for park code `grsm` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's Danger, Caution and
Information categories are the warnings half, split from the rest in dbt.

The inventory also found a PDF, a web page for this club, which other phase B readers take; if one
lands for this type it takes this file, and this note becomes a line in its docstring.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

Staleness risk: April restrictions are still listed in a September file, with no per-item end dates.
Whether they still hold is unverified, so these must not be shown as current without a USFS
cross-check. Skeptic, a second channel that contradicts the first: every `bmta.org` page carries a …

Its `checked` (confirmed 2026-10-03): NPS alerts API, `parkCode=grsm` (the decision 53 inventory,
batch 3, 2026-10-03): 3 (Park Closure 'Park Headquarters Road is closed' 2026-06-26; Park Closure
'Straight Fork ... Balsam Mountain Road closed' 2025-11-12; Information 'Most visitors need a
parking tag'). Tiebreak for the GSMNP fire-ban disagreement. Landed by nps/warnings.py as
nps_alerts. | (coverage audit, 2026-10-01) The same PDF has 5 notices: fireworks always prohibited;
Chattahoochee Stage II fire restriction "lifted 5/4/2026"; Cherokee NF Stage 1 fire restrictions
"beginning April 24, 2026"; Nantahala campfire ban "April 15, 2026"; GSMNP parkwide fire ban
cancelled. Also `bmtamail.org/docs/BeBearPreparedontheBMT.pdf` (static).

Its `where`: https://developer.nps.gov/api/v1/alerts?parkCode=grsm
https://bmtamail.org/docs/BeBearPreparedontheBMT.pdf https://bmta.org

Its `reason`: drawn from nps/'s resources, extracted once there (decision 34); checked names the
layer this org's data arrives in
"""

from extract._kinds import page_notice

CLAIMS = ("bmta_alert_bar",)
RESOURCES = [page_notice("bmta_alert_bar", region=".alert-bar__content", crawl_delay=60.0)]
