"""NWS's active-alerts endpoint and the one check every reader of it applies.

Two readers share these: `export_weather_alerts.py`, which bakes the alerts
over trail squares into `conditions/weather_alerts.json`, and
`extract/_shared/nws/alerts.py`, which lands every active alert in the raw
store for dbt (#1793 — Rebuild the data platform as dlt → dbt: seven
contracted marts, a monthly refresh, published docs, and lighter phone
downloads). They live here, apart from the exporter, because the exporter
imports shapely and `lib.nbm_grid` for its squares, and the extract job
installs neither (`requirements-extract.in`).

The rule they carry is the exporter's: a 200 that is not the GeoJSON
FeatureCollection NWS documents is a changed API, never "no alerts". An empty
list read from a body like that would say "no warnings", which is the one
thing the warnings line must never say by mistake (features/WEATHER.md §5).
"""

from __future__ import annotations

ALERTS_URL = "https://api.weather.gov/alerts/active"

# The media type NWS documents for this route. It answers GeoJSON without it
# today; asking for it says which shape check_response() holds it to.
ACCEPT = "application/geo+json"


def check_response(body: object) -> list[dict]:
    """The alert features, refusing anything that is not the GeoJSON
    FeatureCollection NWS documents. A 200 carrying some other shape is a
    changed API, and publishing its absence of alerts would say "none".

    A page with a next page is refused for the same reason. `/alerts/active`
    answers every active alert in one body and carries no `pagination` today
    (353 alerts in 1.8 MB, 2026-10-01), while `/alerts`, its paged sibling,
    shares the collection's schema. Read as complete, a first page would
    leave every alert on the second out as though it had ended."""
    if not isinstance(body, dict) or body.get("type") != "FeatureCollection" or not isinstance(body.get("features"), list):
        raise RuntimeError(f"{ALERTS_URL} did not answer with a FeatureCollection; refusing to publish its alerts as none")
    if (body.get("pagination") or {}).get("next"):
        raise RuntimeError(f"{ALERTS_URL} answered one page of several; refusing to read it as every active alert")
    return body["features"]
