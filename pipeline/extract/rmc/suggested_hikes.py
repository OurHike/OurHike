"""Randolph Mountain Club: suggested hikes, its Recommended Hikes PDF read here (decision 54 wave 4, section K,
2026-10-04).

- `rmc_recommended_hikes`: Recommended-Hikes-1.pdf, eight pages, 47 walks and routes: 25 Suggested Walks in three
  groups (easy, moderate, strenuous) and 22 Suggested Routes to the Northern Peaks (Madison, Adams, Jefferson),
  each its miles, its ascent in feet, its shape where stated, its trailhead and the document's own time estimate.
  The PDF's Last-Modified is 2023-02-20 and its metadata's dates the same day; it sends no ETag, so the change
  check is its Last-Modified with its Content-Length.

The reader is extract/_pdf_content.py's ContentPdf with the `rmc_recommended_hikes` family, which refuses rather
than relabels a changed layout; facts and the link only, never RMC's descriptions, and no PDF metadata but its
dates (its /Author names a person). Its row in sources.json holds the terms as found, the live read and the
measured key, the walk's group and its name. It needs pypdf, which the extract job installs and fixture mode's
Python does not, so the table lands only from the monthly job, and its base model reads no rows in the fixture
build (extract/_pdf_content.py's docstring).
"""

from extract._pdf_content import content_pdf

CLAIMS = ("rmc_recommended_hikes",)
RESOURCES = [content_pdf("rmc_recommended_hikes")]
