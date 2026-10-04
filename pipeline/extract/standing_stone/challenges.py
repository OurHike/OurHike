"""Standing Stone Trail Club: challenges, the Sweet Sixteen Trail Challenge's points read here (decision 54
wave 5, section K, 2026-10-04).

- `sstc_sweet_16`: /sweet-16-trail-challenge, the 16 points of interest a hiker visits, each its name. The printable
  form's question for each point and the brochure are not read.

The reader is extract/_pages_content.py's ContentPages with the `sstc_sweet_16` site parser: the rows hashed for the
change check (no page validator decides FRESH), one row a place on the challenge's list, its facts and the link,
never the club's prose and never anyone who finished. Its row in sources.json holds the terms as found, the live
read and the measured key, `name`. The End 2 End Challenge is a completion award, and /end-to-end-honorees is its
roster, never read.

The note this replaces read, whole:

Standing Stone Trail Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

The Sweet 16 is a place-based challenge, the same shape as #1780 — Let a club publish a challenge —
places on its own trails that hikers opt into and tag at camp — starting with the ATC's A.T. Summer
Bucket List.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): End 2 End Challenge (`/end-to-end-hiking-information`;
applications "reviewed each year between November 1 and December 31"; `/end-to-end-honorees`). Sweet 16
Trail Challenge (`/sweet-16-trail-challenge`): visit 16 named points and answer a question at each. Its
printable form is `/_files/ugd/30a84d_fedad42032324cbdb3666b1adea3a866.pdf` (212,556 B, Last-Modified
2024-12-29).

Its `where`: https://mapservices.pasda.psu.edu/server/rest/services https://standingstonetrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("sstc_sweet_16",)
RESOURCES = [content_pages("sstc_sweet_16")]
