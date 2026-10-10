"""AMC Connecticut Chapter: challenges, its East of the River Hiker Badge's trails (decision 54's wave 4, section K's
per-site readers, 2026-10-10).

- `amc_ct_eor_hiker_badge`: ct-amc.org's EOR_HikerBadgeForm.pdf (2019), 26 trails east of the Connecticut River on
  its first two pages, each its name and the code of the guidebook that describes it. Nothing after the form's
  'Where to find trail descriptions' line is read: page 3 names the badge committee's members with their home
  addresses and telephone numbers.

The reader is extract/_pdf_content.py's ContentPdf with the `amc_ct_eor_hiker_badge` family: the file's own
Last-Modified and Content-Length decide the change check (it sends no ETag), and its text layer is read through
pypdf, which only the extract job's venv installs, so fixture mode lands no rows for it. ct-amc.org's robots.txt
asks no Crawl-delay (read 2026-10-10). Its row in sources.json holds the terms as found, the live read and the
measured key, the trail's name.
"""

from extract._pdf_content import content_pdf

CLAIMS = ("amc_ct_eor_hiker_badge",)
RESOURCES = [content_pdf("amc_ct_eor_hiker_badge")]
