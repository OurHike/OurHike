"""The Long Path End-to-End Section Guide, one row per section page as lib/nynjtc_long_path_guide.py parses it.

40 sections and 1,256 mile-marked entries, read live 2026-10-01. NYNJTC
publishes no waypoint layer (POI_COVERAGE_SURVEY.md §6), so the guide's prose
is where its lots, lean-tos and springs are. A page the parser does not
recognise raises, so a run never lands the sections that still parsed. The
A.T. shelters and privies NYNJTC maintains arrive through ATC's layers
(`Trail_Club='7'`), extracted in atc/. Not landed: the Shawangunk Ridge
Trail guide (`/srt-g1/`, `/srt-g2/`) in the same skeleton, which the parser
has not been tried on (coverage audit, batch b2_nynjtc).
"""

from extract._kinds import guide_pages

CLAIMS = ("nynjtc_long_path_guide",)
RESOURCES = [guide_pages(key) for key in CLAIMS]
