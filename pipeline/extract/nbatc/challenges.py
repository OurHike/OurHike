"""Natural Bridge Appalachian Trail Club: challenges, the Blue Blazer Program's 20 trails read here (decision
54 wave 4, section K, 2026-10-04).

- `nbatc_blue_blazer`: /pdfs/BlueBlazeTrailHike.pdf, the 20 blue-blazed trails NBATC maintains, each its number,
  name and the A.T. mile it joins at.

The reader is extract/_pdf_content.py's ContentPdf with the `nbatc_blue_blazer` family: a conditional GET with the
file's own validators, one row a place on the challenge's list, its facts and the link, never the club's prose and
never anyone who finished. Its row in sources.json holds the terms as found, the live read and the measured key,
`number`. The 88 Miler Award is a completion award (its form, /pdfs/NBATC88milerform.pdf, not read), and the 100
Mile Club and Hiking Spree are members' tallies of club hikes.
"""

from extract._pdf_content import content_pdf

CLAIMS = ("nbatc_blue_blazer",)
RESOURCES = [content_pdf("nbatc_blue_blazer")]
