"""USGS — The National Map: warnings, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Volcano alerts matter only on volcanic stretches (e.g. Cascades). Neither feed is drought, so both
are in scope for warnings. Debris flow is the more trail-relevant of the two: in a storm, a trail
through a recent burn scar is where a hiker meets one, and the segment layer says which drainages. …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Volcano Hazards Notification Service: "
        "`https://volcanoes.usgs.gov/hans-public/api/volcano/getElevatedVolcanoes` (JSON). Today it returned "
        "elevated volcanoes, e.g. Great Sitkin ORANGE/WATCH, sent 2026-09-30 19:47 UTC. A CAP variant is at "
        "`…/getCapElevated`. Skeptic spot check: 4 elevated today (Great Sitkin ORANGE/WATCH, Kilauea "
        "ORANGE/WATCH, Shishaldin YELLOW/ADVISORY, Ahyi Seamount YELLOW/ADVISORY).",
        "Skeptic adds: post-fire debris-flow hazard assessments. "
        '`https://earthquake.usgs.gov/arcgis/rest/services/ls/pwfdf/MapServer`. Layer 0 "Locations" holds 749 '
        "assessed fires (`fire`, `start_date` …",
    ),
    where=(
        "https://volcanoes.usgs.gov/hans-public/api/volcano/getElevatedVolcanoes",
        "https://earthquake.usgs.gov/arcgis/rest/services/ls/pwfdf/MapServer",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
