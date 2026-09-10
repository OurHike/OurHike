"""One spelling for the UTC timestamp a published artifact carries.

`generated_at` is read by the client's staleness code and diffed between
releases, so two artifacts spelling it two ways is a bug waiting for a
reader. Every exporter that wrote one carried its own copy of this function
- seven by the time export_places.py would have made the eighth (#1371) -
and two spellings had already drifted apart: with and without
`timespec="seconds"`. This is the home; the copies migrate as they are
touched (lib/feature_id.py's own reasoning: a rule two artifacts must agree
on gets one implementation).
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_stamp(value: datetime) -> str:
    """`value` as an ISO-8601 UTC instant to the second, `Z`-suffixed.

    A naive datetime is read as UTC rather than refused: the exporters
    stamp `datetime.now(timezone.utc)`, and a test handing a naive value
    means the same clock."""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
