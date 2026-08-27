"""Publish NYNJTC's Trail Alerts as a static artifact (#1078).

[features/ORG_NOTICES.md](../features/ORG_NOTICES.md) is the design. The
fourth artifact in the family
[CONDITIONS_DELIVERY.md](../features/CONDITIONS_DELIVERY.md) established, and
the first from an organization that is not the ATC:

    conditions/closures.json        verified OurHike closures
    conditions/reports.json         verified public reports
    conditions/atc_updates.json     the ATC's own notices
    conditions/nynjtc_alerts.json   NYNJTC's own notices             (this)

THE INPUT IS THE CACHE, AND THERE IS NO REVIEWED FILE, which is the one
structural difference from `export_atc_updates.py` and needs defending rather
than glossing.

ATC's exporter publishes a file a person typed, plus - since #963 - rows ATC
edited after the day that person last looked. That second gate needs a review
date to measure against, and NYNJTC has never been reviewed, so the gate has
no baseline and cannot be copied. The choice is therefore to publish nothing
until somebody reviews 18 alerts, or to publish what NYNJTC themselves list,
in the weakest form the design allows. This does the second, and the four
rails that make it safe are all things ATC's own automatic path already
relies on:

  1. **Nothing is placed.** Every row ships `place: {"kind": "unplaced"}`
     because `reference/notice_places.json` does not exist yet. No mile, no
     geometry, no map ink - so the confident-wrong-location failure that
     `lib/atc_updates.py` is mostly written against cannot occur here at all.
  2. **Nothing obstructs.** `obstructs_trail` is forced false, exactly as
     `auto_row` forces it for ATC, so an unread notice can never draw a
     barrier across a trail whatever its words say.
  3. **Everything says it is unreviewed.** `review_state` is `unreviewed` on
     every row, which is the field the app uses to say NYNJTC posted this and
     nobody here has checked it.
  4. **Facts and a link only.** Title, locality, NYNJTC's own date and the URL
     of their page. Never their body text - the split that let ATC's notices
     ship without waiting on a redistribution answer, applied unchanged.

WHAT IS DELIBERATELY NOT FILTERED. An alert NYNJTC still lists is an alert
NYNJTC still stands behind, and this publishes on that signal rather than on
a guess about age. Some rows are from 2024; their own `updated_at` says so and
the client renders it. The alternative - dropping anything older than N months
- would be this build overruling the organization that maintains the trail,
which is the wrong direction for a source whose whole value is that they are
the steward. If NYNJTC recategorises or deletes an alert it leaves their API
and the next bake stops carrying it, which is `fetch_atc_updates.py`'s
`listed` reasoning arriving for free.

    python export_nynjtc_alerts.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from lib.hashing import sha256_file
from lib.nynjtc_alerts import UNREVIEWED, published_rows

ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / "data" / "raw" / "nynjtc_alerts.json"
OUT_DIR = ROOT / "data" / "processed" / "conditions"
OUT_PATH = OUT_DIR / "nynjtc_alerts.json"

#: Its own manifest rather than a fifth entry in `conditions_manifest.json`,
#: for the reason `export_atc_updates.py` gives: two scripts writing one file
#: would make the published set depend on which ran last.
MANIFEST_PATH = ROOT / "data" / "processed" / "nynjtc_alerts_manifest.json"

#: Becomes `conditions/<name>.json` in the bucket and the field the client
#: validates the document by. A key in that bucket is a URL deployed clients
#: already request and can never be renamed (lib/r2_keys.py), so it is spelled
#: once, here.
PAYLOAD = "nynjtc_alerts"


def _stamp_utc(value: datetime) -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def load_cache(path: Path | None = None) -> dict:
    """What the last successful fetch learned, or an empty cache.

    An unreadable cache answers empty rather than raising, and `main` then
    publishes nothing - which is the honest outcome of "the fetch has not run
    here". The client reads a missing artifact as no NYNJTC layer at all,
    never as NYNJTC reporting nothing.
    """
    path = path or CACHE_PATH
    try:
        document = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    alerts = document.get("alerts")
    return alerts if isinstance(alerts, dict) else {}


def build_document(alerts: dict, generated_at: datetime) -> dict:
    """The artifact: every alert NYNJTC lists, in the weakest publishable form.

    NO `reviewed_at`, and its absence is load-bearing rather than an omission.
    `export_atc_updates.py` carries one because a person checked ATC's page on
    a date, and the client renders that date. Nobody has checked NYNJTC's, so
    there is no such date to carry, and inventing one - the bake's own clock,
    say - would claim a review that did not happen. The client therefore has
    only `generated_at` to render for this source, which is exactly true: when
    we last looked, not when anybody last judged.
    """
    return {
        "generated_at": _stamp_utc(generated_at),
        PAYLOAD: published_rows(alerts),
    }


def main() -> dict | None:
    alerts = load_cache()
    if not alerts:
        # Not a failure. An empty or missing cache means fetch_nynjtc_alerts.py
        # has not run in this workspace, and publishing an empty artifact would
        # read as "NYNJTC reports nothing" - a different claim from "we have
        # not looked", and the more dangerous of the two.
        print(
            f"No cached NYNJTC alerts at {CACHE_PATH}, so nothing was published. "
            "Run fetch_nynjtc_alerts.py first. An empty artifact would read as "
            "'NYNJTC reports nothing', which is not what an absent cache means."
        )
        return None

    generated_at = datetime.now(timezone.utc)
    rows = published_rows(alerts)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(build_document(alerts, generated_at), indent=2) + "\n")

    manifest = {
        "artifacts": {
            PAYLOAD: {
                "path": str(OUT_PATH),
                "sha256": sha256_file(OUT_PATH),
                "count": len(rows),
                "reviewed_count": 0,
                "automatic_count": len(rows),
                "generated_at": _stamp_utc(generated_at),
            }
        }
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    unplaced = sum(1 for row in rows if row["place"]["kind"] == "unplaced")
    print(
        f"Wrote {len(rows)} NYNJTC alert(s) to {OUT_PATH}: all {len(rows)} {UNREVIEWED}, "
        f"{unplaced} unplaced (no reference/notice_places.json yet - features/ORG_NOTICES.md §4)."
    )
    return manifest


if __name__ == "__main__":
    main()
