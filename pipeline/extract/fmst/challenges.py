"""Friends of the Mountains-to-Sea Trail: challenges, behind the host's challenge, and not landed (decision 54
wave 5, section K, 2026-10-04).

mountainstoseatrail.org answered our agent HTTP 202 with an SG-Captcha challenge on 2026-10-04 (fmst/
suggested_hikes.py), never solved or retried. The /challenges/ pages the coverage audit names (completing the MST,
the 40 Hike Challenge, the Junior Explorer, the birthday challenge) are, as described, completion and tally
awards, and /challenges/hikers-who-have-completed-the-mst/ is a roster.

The note this replaces read, whole:

Friends of the Mountains-to-Sea Trail: challenges, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Pages. Skeptic: the captcha still blocks curl and WebFetch (202, 202 B, on
`/challenges/40-hike-challenge/`). The search index confirms the content (R):; • the 40 Hike Challenge
is "every hike outlined in 'Great Day Hikes on North Carolina's Mountains-to-Sea Trail'", with a patch,
and its form is …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/challenges/` with: `/challenges/completing-the-entire-mst/`
`/challenges/hikers-who-have-completed-the-mst/` `/challenges/40-hike-challenge/`
`/challenges/junior-explorer/` `/challenges/birthday/`

Its `where`: https://mountainstoseatrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=("https://mountainstoseatrail.org/the-trail/ (HTTP 202, SG-Captcha: challenge, 2026-10-04T16:33:02Z)",),
    where=("https://mountainstoseatrail.org/challenges/",),
    reason="behind a challenge (SG-Captcha), not solved; the challenges are completion awards in any case",
)
