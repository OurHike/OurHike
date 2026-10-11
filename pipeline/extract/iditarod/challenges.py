"""Iditarod Historic Trail Alliance: challenges, the Iditarod NHT Passport Stamp Program's sites as its Visitor Guide
lists them (decision 54's wave 4, section K's per-site readers, 2026-10-10).

- `iditarod_passport_stamps`: iditarod100.org's iditarodnhtvisitorguide.pdf, the 'Iditarod NHT Passport Stamp
  Participants' list, 11 sites in 9 towns, each its name and its town. The Alliance's own passport page lists no
  site and says the trail has 9 stamps, which may be one a town; neither says so. The guide's list is from 2018 and
  states no date it holds to.

The reader is extract/_pdf_content.py's ContentPdf with the `iditarod_passport_stamps` family: the file's own ETag
decides the change check, so an unchanged guide (11.8 MB) answers 304 and is not read again, and its text layer is
read through pypdf, which only the extract job's venv installs, so fixture mode lands no rows for it.
www.iditarod100.org's robots.txt asks no Crawl-delay (read 2026-10-10). Its row in sources.json holds the terms as
found, the live read and the measured key, the site's name. The guide's hikes stay a note (its regional sections are
prose with no list of hikes and their facts), not_available.toml's [iditarod.suggested_hikes].
"""

from extract._pdf_content import content_pdf

CLAIMS = ("iditarod_passport_stamps",)
RESOURCES = [content_pdf("iditarod_passport_stamps")]
