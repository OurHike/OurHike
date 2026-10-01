"""opentrail.org's A.T. waypoints, which fill the water sources ATC's own data lacks, as `raw_opentrail__at`.

The data's terms are unconfirmed: opentrail.org's repository carries no
licence, and the maintainer's "open data" was said informally (#98 — Confirm
opentrail.org data-reuse terms with the maintainer). It lands as it is
fetched today, with every user comment left out, and dbt's publication gate
decides what reaches a phone. Its icon meanings are inferred, not documented,
and one was wrong: "r" is roads and gaps, not resupply (#806 — Every
opentrail "r" point publishes as resupply at high confidence, and not one of
them is a shop; fetch_opentrail.py's ICON_LEGEND).
"""

from extract._kinds import opentrail_feed

TYPE = "points_of_interest"
UNREGISTERED = 'a non-registry input: fetch_opentrail.py\'s API_URL is its one home (ELT.md, "What moves")'
RESOURCES = [opentrail_feed()]
