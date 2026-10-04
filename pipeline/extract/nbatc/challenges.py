"""Natural Bridge Appalachian Trail Club: challenges, the Blue Blazer Program's 20 trails read here (decision
54 wave 4, section K, 2026-10-04).

- `nbatc_blue_blazer`: /pdfs/BlueBlazeTrailHike.pdf, the 20 blue-blazed trails NBATC maintains, each its number,
  name and the A.T. mile it joins at.

The reader is extract/_pdf_content.py's ContentPdf with the `nbatc_blue_blazer` family: a conditional GET with the
file's own validators, one row a place on the challenge's list, its facts and the link, never the club's prose and
never anyone who finished. Its row in sources.json holds the terms as found, the live read and the measured key,
`number`. The 88 Miler Award is a completion award (its form, /pdfs/NBATC88milerform.pdf, not read), and the 100
Mile Club and Hiking Spree are members' tallies of club hikes.

The note this replaces read, whole:

Natural Bridge Appalachian Trail Club: challenges, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

The Blue Blazer list is the closest thing in this batch to #1780's opt-in place list. It is a PDF table,
so extracting it is a reviewed transcription, not a fetch.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Blue Blazer Program,
`https://home.nbatc.org/pdfs/BlueBlazeTrailHike.pdf` (2026-07-09): a patch for hiking all 20
NBATC-maintained blue-blazed trails. Each is listed with its A.T. junction and mileage; honor system, no
time limit, $5 for non-members. 88 Miler Award, `/pdfs/NBATC88milerform.pdf` (2026-08-27): complete
NBATC's A.T. miles. The 100 Mile Club and Hiking Spree are members' tallies of club hikes

Its `where`: https://home.nbatc.org/pdfs/BlueBlazeTrailHike.pdf https://nbatc.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pdf_content import content_pdf

CLAIMS = ("nbatc_blue_blazer",)
RESOURCES = [content_pdf("nbatc_blue_blazer")]
