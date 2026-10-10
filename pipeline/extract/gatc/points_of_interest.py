"""GATC's water-sources PDF, one row per source as lib/club_pdfs.py parses it: review only.

65 rows when the coverage audit read it; the file's `Last-Modified` reads
2026-03-02 while its embedded title is "GATC Water Update July 2020"
(WATER_SOURCES.md §4). The registry row carries `reaches_hikers: false` and
`licence_basis: unresolved` until GATC answers the redistribution ask, so it
lands and reaches no mart (ELT.md, "GATC's PDF stays review-only"). The
shelters, campsites, privies and parking GATC maintains arrive through ATC's
layers (`Trail_Club='30'`), extracted in atc/points_of_interest.py (coverage
audit 2026-10-01, batch b4_oprhp_mohonk_gatc).
"""

from extract._kinds import club_pdf

CLAIMS = ("gatc_water_sources",)
RESOURCES = [club_pdf(key) for key in CLAIMS]
