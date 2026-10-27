"""Read the three layers into a raw directory, asking each host's robots.txt first.

    raw/csi.json          every CSI row's attributes (CSI_FIELDS only), plus the layer's metadata
    raw/parking.geojson   ATC's parking points
    raw/padus.geojson     the PAD-US polygons containing at least one CSI site
    raw/centerline.geojson  ATC's A.T. centerline, simplified to about 5 m

The raw directory is under the gitignored data/ (apps/steward/pipeline/.gitignore).
It holds 2,411 user-created campsite locations, so it never goes in a commit,
an Actions artifact or a public bucket: PLAN.md's opening section.

ROBOTS.TXT FOLLOWS RFC 9309, as pipeline/extract/_robots.py does for OurHike's
own fetches: a 2xx is the rules, a 4xx other than 429 means there are none, and
anything else (a 5xx, a 429, no answer) refuses the whole host. All three
ArcGIS hosts answered 403 on 2026-10-26, which is "no rules". The matching is
urllib.robotparser's, which predates the RFC and differs from it at the edges
(wildcards, longest-match). That is good enough for a job that asks three
query endpoints, and it is the reason this is not a general crawler.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

from steward_analysis import sources

#: ArcGIS caps a page at the layer's maxRecordCount, 2,000 on the CSI layer
#: (read 2026-10-24); 1,000 keeps each answer comfortably under it.
PAGE_SIZE = 1000

#: Sites per PAD-US query. The geometry travels in a POST body; 40 points kept
#: each answer to a handful of polygons in the planning spike.
PADUS_BATCH = 40

#: PAD-US polygons are simplified to this many degrees (about 10 m) on the
#: server. A site within 10 m of a unit boundary can land on the wrong side of
#: it; a camping rule never turns on a distance that fine.
PADUS_SIMPLIFY_DEG = 0.0001

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
RETRY_WAITS_S = (2, 4, 8)


class RefusedByRobots(RuntimeError):
    pass


class Fetcher:
    """One requests session, the job's User-Agent, robots.txt read once per host, and a few retries."""

    def __init__(self, session: requests.Session | None = None, sleep=time.sleep):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = sources.USER_AGENT
        self.sleep = sleep
        self._robots: dict[str, RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            self._robots[origin] = self._read_robots(origin)
        rules = self._robots[origin]
        return True if rules is None else rules.can_fetch(sources.PRODUCT_TOKEN, url)

    def _read_robots(self, origin: str) -> RobotFileParser | None:
        try:
            resp = self.session.get(f"{origin}/robots.txt", timeout=30)
        except requests.RequestException as exc:
            raise RefusedByRobots(f"{origin}/robots.txt could not be read ({exc}); RFC 9309 treats that as disallow-all") from exc
        if 200 <= resp.status_code < 300:
            parser = RobotFileParser()
            parser.parse(resp.text.splitlines())
            return parser
        if 400 <= resp.status_code < 500 and resp.status_code != 429:
            return None
        raise RefusedByRobots(f"{origin}/robots.txt answered {resp.status_code}; RFC 9309 treats that as disallow-all")

    def request(self, method: str, url: str, **kwargs) -> dict:
        if not self.allowed(url):
            raise RefusedByRobots(f"robots.txt disallows {url} for {sources.PRODUCT_TOKEN}")
        for wait in (*RETRY_WAITS_S, None):
            resp = self.session.request(method, url, timeout=120, **kwargs)
            if resp.status_code in RETRY_STATUSES and wait is not None:
                self.sleep(wait)
                continue
            resp.raise_for_status()
            body = resp.json()
            # ArcGIS reports most failures as HTTP 200 with an "error" member.
            if isinstance(body, dict) and "error" in body:
                raise RuntimeError(f"{url} answered an error: {body['error']}")
            return body
        raise AssertionError("unreachable: the last attempt either returns or raises")


def fetch_csi(fetcher: Fetcher) -> dict:
    """Every CSI row, paged by object id, checked against the layer's own count."""
    layer = fetcher.request("GET", sources.CSI_LAYER, params={"f": "json"})
    query = f"{sources.CSI_LAYER}/query"
    expected = fetcher.request("GET", query, params={"where": "1=1", "returnCountOnly": "true", "f": "json"})["count"]
    rows: list[dict] = []
    while True:
        page = fetcher.request(
            "GET",
            query,
            params={
                "where": "1=1",
                "outFields": ",".join(sources.CSI_FIELDS),
                "returnGeometry": "false",
                "orderByFields": "OBJECTID",
                "resultOffset": len(rows),
                "resultRecordCount": PAGE_SIZE,
                "f": "json",
            },
        )
        batch = [f["attributes"] for f in page.get("features", [])]
        rows.extend(batch)
        # A full page, or one the server flags as cut short, means there may be more.
        if not batch or (len(batch) < PAGE_SIZE and not page.get("exceededTransferLimit")):
            break
    if len(rows) != expected:
        raise RuntimeError(f"CSI layer reported {expected} rows and {len(rows)} came back; refusing to score a partial layer")
    edited = (layer.get("editingInfo") or {}).get("dataLastEditDate")
    return {"layer": sources.CSI_LAYER, "data_last_edit_ms": edited, "rows": rows}


def fetch_parking(fetcher: Fetcher) -> dict:
    return fetcher.request(
        "GET",
        f"{sources.PARKING_LAYER}/query",
        params={"where": "1=1", "outFields": ",".join(sources.PARKING_FIELDS), "outSR": 4326, "f": "geojson"},
    )


def fetch_padus(fetcher: Fetcher, points: list[tuple[float, float]]) -> dict:
    """The PAD-US polygons containing any of `points` (lon, lat), each polygon once."""
    by_id: dict = {}
    ordered = sorted(points, key=lambda p: (p[1], p[0]))
    for start in range(0, len(ordered), PADUS_BATCH):
        batch = ordered[start : start + PADUS_BATCH]
        geometry = {"points": [list(p) for p in batch], "spatialReference": {"wkid": 4326}}
        page = fetcher.request(
            "POST",
            f"{sources.PADUS_LAYER}/query",
            data={
                "geometry": json.dumps(geometry),
                "geometryType": "esriGeometryMultipoint",
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": ",".join(sources.PADUS_FIELDS),
                "returnGeometry": "true",
                "outSR": 4326,
                "maxAllowableOffset": PADUS_SIMPLIFY_DEG,
                "f": "geojson",
            },
        )
        for feature in page.get("features", []):
            by_id.setdefault(feature["properties"]["OBJECTID"], feature)
    return {"type": "FeatureCollection", "features": list(by_id.values())}


def fetch_centerline(fetcher: Fetcher) -> dict:
    """ATC's centerline as GeoJSON, paged by offset and checked against the layer's own count."""
    query = f"{sources.CENTERLINE_LAYER}/query"
    expected = fetcher.request("GET", query, params={"where": "1=1", "returnCountOnly": "true", "f": "json"})["count"]
    features: list[dict] = []
    while len(features) < expected:
        page = fetcher.request(
            "GET",
            query,
            params={
                "where": "1=1",
                "outFields": "OBJECTID",
                "returnGeometry": "true",
                "maxAllowableOffset": sources.CENTERLINE_SIMPLIFY_DEG,
                "outSR": 4326,
                "orderByFields": "OBJECTID",
                "resultOffset": len(features),
                "resultRecordCount": PAGE_SIZE,
                "f": "geojson",
            },
        )
        batch = page.get("features", [])
        if not batch:
            break
        features.extend(batch)
    if len(features) != expected:
        raise RuntimeError(f"centerline reported {expected} segments and {len(features)} came back; refusing a partial trail")
    return {"type": "FeatureCollection", "features": features}


def fetch_all(raw_dir: Path, fetcher: Fetcher | None = None) -> None:
    fetcher = fetcher or Fetcher()
    raw_dir.mkdir(parents=True, exist_ok=True)
    csi = fetch_csi(fetcher)
    (raw_dir / "csi.json").write_text(json.dumps(csi))
    (raw_dir / "parking.geojson").write_text(json.dumps(fetch_parking(fetcher)))
    points = [(r["Longitude"], r["Latitude"]) for r in csi["rows"] if r.get("Longitude") is not None]
    (raw_dir / "padus.geojson").write_text(json.dumps(fetch_padus(fetcher, points)))
    (raw_dir / "centerline.geojson").write_text(json.dumps(fetch_centerline(fetcher)))
