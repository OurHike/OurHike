"""Cumberland Trail / Tennessee State Parks: suggested hikes, held because the host refuses our agent
(decision 54 wave 3, section C, 2026-10-04).

tnstateparks.com's JSON:API (`/jsonapi/node/trails`, 26 Cumberland Trail nodes, the coverage audit)
is machine-readable, and the host refuses lib/user_agent.py's agent (the dlt skill, 'Never imitate a
browser': "tnstateparks.com and LSHT's ClubExpress files refuse our agent, so they hold until the
org answers"). Nothing is sent under another agent (decision 39), so this waits for Tennessee State
Parks.

The note this replaces read, whole:

Cumberland Trail / Tennessee State Parks: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Section-by-section descriptions, already numbered, are the most structured hike source in the batch.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "The dlt skill's record that tnstateparks.com refuses our agent (decision 39's poll, 2026-10-01); nothing on the host was asked today.",
        '(the coverage audit, 2026-10-01) JSON:API `https://tnstateparks.com/jsonapi/node/trails` with a title filter on "Cumberland": 26 CT trail nodes, each with `field_trail_length`, `field_trail_difficulty`, `field_trails_status`, `body`, `field_trail_geometry`. Example: "(4) Cumberland Trail - North Cumberland WMA Section - Cove Lake Section", 47.30 mi, difficult. Pages: `/parks/cumberland-trail/hiking`, `/parks/activity-detail/cumberland-trail-hiking`.',
    ),
    where=(
        "https://tnstateparks.com/jsonapi/node/trails",
        "https://tnstateparks.com/",
    ),
    reason="refused: the host refuses our named agent, and the pipeline never imitates a browser (decision 39)",
)
