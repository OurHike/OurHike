"""Measure the open sources that carry a *current* low-water signal near the A.T.

[WATER_SOURCES.md](WATER_SOURCES.md) answers "where is water" and closes with
the line this spike exists to test: "nothing open carries reliability", and
"flowing *today* belongs to DATA_NUDGES.md's one-tap loop". That was a
statement about *map* data - point inventories, spring layers, NHD's
perennial/intermittent FCode. It was never measured against the hydrological
and drought monitoring column, which is a different set of publishers asking
a different question, and this is that measurement.

WHAT IS MEASURED, AND WHY EACH ONE

  1. USGS streamgauges. Distance from every active real-time discharge gauge
     in the fourteen trail states to the centerline, then - for the ones close
     enough to mean anything - today's flow against that gauge's own
     day-of-year percentiles of record. A percentile is the only figure any of
     these sources publishes that says "low" rather than "some number of cubic
     feet per second", which is the whole reason this file computes them.
  2. USGS real-time groundwater wells. A ridgeline spring is groundwater
     discharge, so a shallow well's level is closer in physics to a spring
     than a river gauge is. Counted the same way, against the same centerline.
  3. NOAA's National Water Model, via the NWPS API. The only source that
     publishes a flow number for the *headwater* reaches the trail actually
     walks past. Sampled along the whole corridor, and counted against the
     NWM retrospective's own reach index to size what a per-reach "is this
     low for the date" baseline would cost.
  4. The U.S. Drought Monitor. This week's polygons intersected with the
     centerline, in trail miles per class, plus a cross-tabulation against
     (1)'s percentile bands - two independent publishers, one of them a
     weekly human consensus and the other an instrument, agreeing or not.

WHAT IS NOT MEASURED HERE

Nothing is validated against an observed dry spring, because no such
observation set exists openly for this trail (WATER_SOURCES.md §4 measured
that too). Everything below is coverage, currency and cross-source
coherence - which is what can be checked without a hiker on the ground, and
is not the same thing as accuracy. WATER_CONDITIONS.md holds the findings and
says which grade each claim carries.

ENDPOINT NOTE, AND IT IS LOAD-BEARING

The percentile figures come from `waterservices.usgs.gov/nwis/stat/`, which
USGS is decommissioning in Q1 2027 and has said may degrade from the second
half of 2026 - i.e. now. Its replacement, `api.waterdata.usgs.gov`, serves
daily values but *no* precomputed percentiles (checked 2026-08-15: the
collection list has none). Anything built on this measurement computes its
own percentiles from the daily record. This script keeps using the legacy
endpoint deliberately, because a spike that stops reproducing when the
endpoint dies is a spike whose expiry is visible.

Every upstream response is cached under OUT_DIR, so a re-run re-reports
without re-fetching and an interrupted run resumes.
"""

from __future__ import annotations

import datetime
import gzip
import json
import math
import os
import time
import urllib.parse
import urllib.request

OUT_DIR = os.environ.get("OUT_DIR", "data/spike")

CENTERLINE = "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Centerline/FeatureServer/0/query"
USGS_SITE = "https://waterservices.usgs.gov/nwis/site/"
USGS_IV = "https://waterservices.usgs.gov/nwis/iv/"
USGS_STAT = "https://waterservices.usgs.gov/nwis/stat/"
NLDI_POSITION = "https://api.water.usgs.gov/nldi/linked-data/comid/position"
NWPS_REACH = "https://api.water.noaa.gov/nwps/v1/reaches"
USDM_CURRENT = "https://droughtmonitor.unl.edu/data/json/usdm_current.json"
NWM_RETRO_ZARR = "https://noaa-nwm-retrospective-3-0-pds.s3.amazonaws.com/CONUS/zarr/chrtout.zarr/"

STATE_CODES = "ga nc tn va wv md pa nj ny ct ma vt nh me".split()

# Gauges further out than this are measuring a different mountain. 20 km is
# not a hydrological threshold - it is the distance at which the count stops
# growing usefully (§1 of WATER_CONDITIONS.md carries the curve it came from).
NEAR_TRAIL_M = 20_000

# A gauge on a big river integrates hundreds of tributaries and answers a
# question about the valley, not the ridge. 50 sq mi is the screen this spike
# reports separately; it is a judgement, not a finding.
SMALL_CATCHMENT_SQMI = 50.0

# NWM's own missing-value sentinel arrives through the NWPS API as a plain
# number rather than a null. Measured 2026-08-15: two of 59 sampled reaches
# (Watauga River, TN and Dead River, ME) returned it for every hour of the
# series, so it is common enough to be a filter rather than a curiosity.
NWM_MISSING = -9999.0

# Half-width of the corridor a shippable drought layer would be clipped to.
# 0.09 degrees is about 10 km, which is wide enough that the band still reads
# as a region on a zoomed-out map rather than as a stripe on the trail.
CORRIDOR_BUFFER_DEG = 0.09

# The other two steps of export_drought.py's corridor, kept in step with it so
# the layer size measured here is the artifact that ships. ~110 m before the
# buffer (which is what makes buffering a 690,040-vertex line affordable at
# all: 235 s measured without it) and ~550 m after it.
CORRIDOR_SIMPLIFY_DEG = 0.001
CORRIDOR_SMOOTH_DEG = 0.005

EARTH_R_M = 6_371_008.8


def _cache(name: str, produce):
    """Run `produce` once, keep its JSON under OUT_DIR, re-read it thereafter.

    The write goes through a temporary file and a rename, because the first
    version of this did not: a run interrupted part-way through writing the
    12 MB centerline left a truncated file behind, and every later run
    crashed on it rather than re-fetching. A cache that can poison itself is
    worse than no cache.
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    value = produce()
    partial = path + ".partial"
    with open(partial, "w") as fh:
        json.dump(value, fh)
    os.replace(partial, path)
    return value


def _get(url: str, timeout: int = 240) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def _get_json(url: str, timeout: int = 240):
    return json.loads(_get(url, timeout))


def _rdb_rows(text: str):
    """USGS RDB is tab-separated with a comment block and a format-spec row."""
    header = None
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        fields = line.split("\t")
        if header is None:
            header = fields
            continue
        if fields and fields[0].endswith("s") and fields[0][:-1].isdigit():
            continue  # the "5s 15s 50s" width row
        yield dict(zip(header, fields))


def haversine_m(a, b) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R_M * math.asin(math.sqrt(h))


# --------------------------------------------------------------------------
# The trail itself


def fetch_centerline_parts():
    """ATC's centerline, one coordinate list per feature.

    Keeping the parts separate matters: concatenating all 3,027 of them into
    one line draws a jump between every pair and measures the A.T. at 108,000
    miles instead of 2,172. That mistake was made once while writing this.
    """

    def produce():
        parts, offset = [], 0
        while True:
            params = dict(
                where="1=1",
                outFields="",
                returnGeometry="true",
                f="geojson",
                outSR="4326",
                geometryPrecision="5",
                resultOffset=str(offset),
                resultRecordCount="2000",
            )
            page = _get_json(CENTERLINE + "?" + urllib.parse.urlencode(params))
            features = page.get("features", [])
            if not features:
                break
            for feature in features:
                geometry = feature.get("geometry") or {}
                if geometry.get("type") == "LineString":
                    parts.append(geometry["coordinates"])
                elif geometry.get("type") == "MultiLineString":
                    parts.extend(geometry["coordinates"])
            offset += len(features)
            if len(features) < 2000 and not page.get("properties", {}).get("exceededTransferLimit"):
                break
        return [part for part in parts if len(part) > 1]

    return _cache("at_centerline_parts.json", produce)


class TrailIndex:
    """Distance from a point to the centerline, bucketed by tenth-of-a-degree."""

    def __init__(self, parts, stride: int = 5):
        self.buckets: dict[float, list] = {}
        for part in parts:
            for point in part[::stride]:
                self.buckets.setdefault(round(point[1], 1), []).append(point)

    def distance_m(self, lon: float, lat: float, search_deg: float = 1.0) -> float:
        best = float("inf")
        key = round(lat, 1)
        steps = int(search_deg * 10)
        for step in range(-steps, steps + 1):
            for point in self.buckets.get(round(key + step / 10.0, 1), ()):
                if abs(point[0] - lon) > 1.5:
                    continue
                distance = haversine_m(point, (lon, lat))
                if distance < best:
                    best = distance
        return best


def trail_miles(parts) -> float:
    total = 0.0
    for part in parts:
        for i in range(1, len(part)):
            total += haversine_m(part[i - 1], part[i])
    return total / 1609.344


# --------------------------------------------------------------------------
# 1. Streamgauges


def fetch_sites(parameter_cd: str, site_type: str, cache_name: str):
    def produce():
        sites = {}
        for state in STATE_CODES:
            params = dict(
                format="rdb",
                stateCd=state,
                siteStatus="active",
                hasDataTypeCd="iv",
                parameterCd=parameter_cd,
                siteType=site_type,
            )
            try:
                text = _get(USGS_SITE + "?" + urllib.parse.urlencode(params)).decode("utf-8", "replace")
            except Exception as exc:  # a state with no such sites answers 404
                print(f"  {state}: none ({exc})")
                continue
            count = 0
            for row in _rdb_rows(text):
                if row.get("agency_cd") != "USGS":
                    continue
                try:
                    lat = float(row["dec_lat_va"])
                    lon = float(row["dec_long_va"])
                except (KeyError, ValueError):
                    continue
                sites[row["site_no"]] = dict(
                    site=row["site_no"],
                    name=row.get("station_nm", ""),
                    lat=lat,
                    lon=lon,
                    huc=row.get("huc_cd", ""),
                    state=state,
                )
                count += 1
            print(f"  {state}: {count}")
        return list(sites.values())

    return _cache(cache_name, produce)


def fetch_drainage_areas(site_ids):
    def produce():
        areas = {}
        for start in range(0, len(site_ids), 100):
            chunk = ",".join(site_ids[start : start + 100])
            params = dict(format="rdb,1.0", sites=chunk, siteOutput="expanded", siteStatus="all")
            text = _get(USGS_SITE + "?" + urllib.parse.urlencode(params)).decode("utf-8", "replace")
            for row in _rdb_rows(text):
                area = (row.get("drain_area_va") or "").strip()
                if row.get("site_no"):
                    areas[row["site_no"]] = area
        return areas

    return _cache("usgs_drainage_areas.json", produce)


def fetch_current_flows(site_ids):
    def produce():
        latest = {}
        for start in range(0, len(site_ids), 60):
            params = dict(format="json", sites=",".join(site_ids[start : start + 60]), parameterCd="00060")
            try:
                payload = _get_json(USGS_IV + "?" + urllib.parse.urlencode(params))
            except Exception as exc:
                print(f"  instantaneous values failed for a batch: {exc}")
                continue
            for series in payload["value"]["timeSeries"]:
                values = series["values"][0]["value"]
                if not values:
                    continue
                site = series["sourceInfo"]["siteCode"][0]["value"]
                try:
                    latest[site] = [float(values[-1]["value"]), values[-1]["dateTime"]]
                except ValueError:
                    continue
        return latest

    return _cache("usgs_current_flow.json", produce)


def fetch_day_of_year_stats(site_ids, month: int, day: int):
    """Percentiles of record for one calendar day, per gauge.

    One request per gauge, which is slow and is the reason this is cached.
    """

    def produce():
        stats = {}
        for i, site in enumerate(site_ids):
            params = dict(
                format="rdb",
                sites=site,
                statReportType="daily",
                statTypeCd="p05,p10,p20,p25,p50,p75,p90",
                parameterCd="00060",
            )
            try:
                text = _get(USGS_STAT + "?" + urllib.parse.urlencode(params)).decode("utf-8", "replace")
            except Exception:
                continue
            for row in _rdb_rows(text):
                try:
                    if int(row["month_nu"]) == month and int(row["day_nu"]) == day:
                        stats[site] = row
                        break
                except (KeyError, ValueError):
                    continue
            if i % 25 == 0:
                print(f"  statistics {i}/{len(site_ids)}")
            time.sleep(0.15)
        return stats

    return _cache(f"usgs_stats_{month:02d}{day:02d}.json", produce)


def flow_band(flow: float, percentiles: dict) -> str:
    """USGS's own streamflow-condition wording, and the thresholds behind it.

    "Much below normal" is <10th percentile and "below normal" 10th-25th on
    every USGS streamflow-conditions map; this keeps those cut points so the
    number here means what it means on their map rather than something new.
    """
    if flow < percentiles["p10"]:
        return "much below normal (<p10)"
    if flow < percentiles.get("p25", percentiles["p50"]):
        return "below normal (p10-p25)"
    if flow < percentiles.get("p75", float("inf")):
        return "normal (p25-p75)"
    return "above normal (>p75)"


def measure_gauges(index: TrailIndex):
    print("Active real-time discharge gauges, by state:")
    gauges = fetch_sites("00060", "ST", "usgs_discharge_sites.json")
    for gauge in gauges:
        gauge.setdefault("d_m", index.distance_m(gauge["lon"], gauge["lat"]))
    gauges.sort(key=lambda g: g["d_m"])
    print(f"\ntotal active real-time discharge gauges in the fourteen states: {len(gauges)}")
    for radius in (1_000, 2_000, 5_000, 10_000, 20_000, 50_000):
        print(f"  within {radius:6d} m of the centerline: {sum(1 for g in gauges if g['d_m'] <= radius)}")

    near = [g for g in gauges if g["d_m"] <= NEAR_TRAIL_M]
    ids = [g["site"] for g in near]
    areas = fetch_drainage_areas(ids)
    current = fetch_current_flows(ids)
    today = datetime.date.today()
    stats = fetch_day_of_year_stats(ids, today.month, today.day)

    rows = []
    for gauge in near:
        site = gauge["site"]
        if site not in current or site not in stats:
            continue
        row = stats[site]
        try:
            percentiles = {
                key: float(row[key + "_va"]) for key in ("p05", "p10", "p20", "p25", "p50", "p75", "p90") if row.get(key + "_va")
            }
        except ValueError:
            continue
        if "p10" not in percentiles or "p50" not in percentiles:
            continue
        flow = current[site][0]
        rows.append(
            dict(
                site=site,
                name=gauge["name"],
                state=gauge["state"],
                d_km=round(gauge["d_m"] / 1000, 1),
                lat=gauge["lat"],
                lon=gauge["lon"],
                flow_cfs=flow,
                p10=percentiles["p10"],
                p50=percentiles["p50"],
                years=int(row["end_yr"]) - int(row["begin_yr"]) + 1,
                drain_sqmi=areas.get(site, ""),
                band=flow_band(flow, percentiles),
            )
        )

    print(f"\ngauges within {NEAR_TRAIL_M // 1000} km with both a current value and day-of-year statistics: {len(rows)}")
    _report_bands(rows, "all")
    small = [r for r in rows if _is_small(r["drain_sqmi"])]
    print(f"\nof those, drainage area < {SMALL_CATCHMENT_SQMI:.0f} sq mi: {len(small)}")
    _report_bands(small, "small catchments")
    years = sorted(r["years"] for r in rows)
    if years:
        print(
            "record length: min %d, median %d, max %d years; %d have >= 30"
            % (years[0], years[len(years) // 2], years[-1], sum(1 for y in years if y >= 30))
        )
    with open(os.path.join(OUT_DIR, "gauge_conditions.json"), "w") as fh:
        json.dump(rows, fh, indent=1)
    return rows


def _is_small(area: str) -> bool:
    try:
        return float(area) < SMALL_CATCHMENT_SQMI
    except (TypeError, ValueError):
        return False


def _report_bands(rows, label: str):
    if not rows:
        return
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["band"]] = counts.get(row["band"], 0) + 1
    for band, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print("  %-26s %3d  (%.0f%%)  [%s]" % (band, count, 100 * count / len(rows), label))


# --------------------------------------------------------------------------
# 2. Groundwater wells


def measure_wells(index: TrailIndex):
    print("\nActive real-time groundwater-level wells, by state:")
    wells = fetch_sites("72019", "GW", "usgs_groundwater_sites.json")
    for well in wells:
        well.setdefault("d_m", index.distance_m(well["lon"], well["lat"]))
    wells.sort(key=lambda w: w["d_m"])
    print(f"total active real-time groundwater wells in the fourteen states: {len(wells)}")
    for radius in (5_000, 10_000, 20_000, 50_000):
        print(f"  within {radius:6d} m of the centerline: {sum(1 for w in wells if w['d_m'] <= radius)}")
    return wells


# --------------------------------------------------------------------------
# 3. The National Water Model


def sample_nwm(parts, count: int = 60):
    """Walk the corridor, ask NLDI which NHD reach each point sits on, ask NWPS its flow."""

    def produce():
        points = [point for part in parts for point in part]
        stride = max(1, len(points) // count)
        rows = []
        for lon, lat in [points[i * stride] for i in range(count)]:
            try:
                query = urllib.parse.urlencode({"coords": f"POINT({lon} {lat})", "f": "json"})
                located = _get_json(f"{NLDI_POSITION}?{query}", timeout=120)
                properties = located["features"][0]["properties"]
                comid = properties.get("identifier") or properties.get("comid")
                payload = _get_json(f"{NWPS_REACH}/{comid}/streamflow?series=analysis_assimilation", timeout=120)
                series = payload["analysisAssimilation"]["series"]
                flows = [float(entry["flow"]) for entry in series["data"]]
                rows.append(
                    dict(
                        lon=lon,
                        lat=lat,
                        comid=comid,
                        name=payload["reach"].get("name") or "",
                        latest_cfs=flows[-1] if flows else None,
                        hours=len(flows),
                        units=series["units"],
                    )
                )
            except Exception as exc:
                print(f"  reach lookup failed at {lon:.4f},{lat:.4f}: {exc}")
            time.sleep(0.2)
        return rows

    rows = _cache("nwm_sample.json", produce)
    usable = [r for r in rows if r["latest_cfs"] is not None]
    missing = [r for r in usable if r["latest_cfs"] == NWM_MISSING]
    real = [r for r in usable if r["latest_cfs"] != NWM_MISSING]
    zero = [r for r in real if r["latest_cfs"] == 0.0]
    print(f"\nNWM reaches sampled along the corridor: {len(usable)}")
    print(f"  serving the {NWM_MISSING} missing-value sentinel as a number: {len(missing)}")
    print(f"  reporting exactly 0.000 cfs right now: {len(zero)} of {len(real)}")
    if real:
        flows = sorted(r["latest_cfs"] for r in real)
        print(
            "  flow quartiles cfs: %.2f / %.2f / %.2f / %.2f / %.2f"
            % (flows[0], flows[len(flows) // 4], flows[len(flows) // 2], flows[3 * len(flows) // 4], flows[-1])
        )
    return rows


def measure_nwm_retrospective_cost(parts):
    """How many NWM reaches sit on the trail, and what a baseline would cost to build.

    "Is this reach low for the date" needs a per-reach climatology, and the
    only published one is the retrospective's own hourly record. This reads
    the store's coordinate arrays (a few tens of MB) and its chunk layout to
    turn that into a number rather than an impression.
    """
    try:
        import numcodecs
        import numpy as np
    except ImportError:
        print("\n(numpy/numcodecs not installed - skipping the retrospective sizing)")
        return None

    meta = _get_json(NWM_RETRO_ZARR + ".zmetadata")["metadata"]

    def read_1d(name):
        spec = meta[f"{name}/.zarray"]
        raw = _get(NWM_RETRO_ZARR + f"{name}/0", timeout=900)
        codec = spec.get("compressor") or {}
        if codec.get("id") == "zstd":
            raw = numcodecs.Zstd().decode(raw)
        elif codec.get("id") == "blosc":
            raw = numcodecs.Blosc().decode(raw)
        elif codec.get("id") == "zlib":
            import zlib

            raw = zlib.decompress(raw)
        return np.frombuffer(raw, dtype=spec["dtype"])

    lat = read_1d("latitude")
    lon = read_1d("longitude")
    order = read_1d("order")

    sample = np.array([point for part in parts for point in part][::20])
    in_box = (
        (lon > sample[:, 0].min() - 0.05)
        & (lon < sample[:, 0].max() + 0.05)
        & (lat > sample[:, 1].min() - 0.05)
        & (lat < sample[:, 1].max() + 0.05)
    )
    candidates = np.nonzero(in_box)[0]

    lat_buckets: dict[float, list] = {}
    for point in sample:
        lat_buckets.setdefault(round(float(point[1]), 1), []).append(point)

    near = []
    for i in candidates:
        point_lat, point_lon = float(lat[i]), float(lon[i])
        nearby = []
        key = round(point_lat, 1)
        for step in (-1, 0, 1):
            nearby.extend(lat_buckets.get(round(key + step / 10.0, 1), ()))
        if not nearby:
            continue
        nearby = np.array(nearby)
        dx = (nearby[:, 0] - point_lon) * math.cos(math.radians(point_lat)) * 111_320.0
        dy = (nearby[:, 1] - point_lat) * 110_574.0
        if float(np.min(dx * dx + dy * dy)) <= 2000.0**2:
            near.append(i)
    near = np.array(near)

    orders = {int(o): int((order[near] == o).sum()) for o in np.unique(order[near])}
    blocks = sorted({int(i) // 30000 for i in near})
    time_steps, reaches = meta["streamflow/.zarray"]["shape"]
    chunk_time, chunk_reach = meta["streamflow/.zarray"]["chunks"]
    time_chunks = -(-time_steps // chunk_time)
    chunk_mb = chunk_time * chunk_reach * 4 / 1e6
    total_tb = time_chunks * len(blocks) * chunk_mb / 1e6

    print(f"\nNWM reaches within 2 km of the centerline: {len(near)}")
    print(f"  by stream order: {orders}")
    print(f"  retrospective: {time_steps} hourly steps x {reaches} reaches, chunked {chunk_time}x{chunk_reach}")
    print(f"  those reaches fall in {len(blocks)} of {-(-reaches // chunk_reach)} reach blocks")
    print(f"  a full per-reach climatology would read {time_chunks * len(blocks)} chunks ~ {total_tb:.1f} TB uncompressed")
    return dict(reaches=len(near), orders=orders, blocks=len(blocks), tb=total_tb)


# --------------------------------------------------------------------------
# 4. The U.S. Drought Monitor


def measure_drought(parts, gauge_rows):
    try:
        from shapely.geometry import MultiLineString, Point, shape
        from shapely.ops import unary_union
    except ImportError:
        print("\n(shapely not installed - skipping the drought overlay)")
        return None

    payload = _cache("usdm_current.json", lambda: _get_json(USDM_CURRENT))
    by_class: dict[int, list] = {}
    for feature in payload["features"]:
        by_class.setdefault(feature["properties"]["DM"], []).append(shape(feature["geometry"]))
    classes = {key: unary_union(value).buffer(0) for key, value in by_class.items()}

    line = MultiLineString(parts)
    total = trail_miles(parts)

    def measure_part(geometry):
        return trail_miles(piece_lines(geometry))

    measure_class_overlap(classes)

    names = {
        0: "D0 abnormally dry",
        1: "D1 moderate drought",
        2: "D2 severe drought",
        3: "D3 extreme drought",
        4: "D4 exceptional drought",
    }
    print(f"\nA.T. centerline: {total:.1f} mi across {len(parts)} parts")
    print("miles inside each U.S. Drought Monitor class (the classes are disjoint - see above):")
    miles = {}
    for level in sorted(classes):
        miles[level] = measure_part(line.intersection(classes[level]))
        print("  %-24s %7.1f mi  (%.1f%%)" % (names[level], miles[level], 100 * miles[level] / total))
    affected = sum(miles.values())
    print("  %-24s %7.1f mi  (%.1f%%)" % ("any class at all", affected, 100 * affected / total))
    print("  %-24s %7.1f mi  (%.1f%%)" % ("no class at all", total - affected, 100 * (total - affected) / total))

    if gauge_rows:
        print("\ngauge flow band against the drought class at the gauge:")
        levels = [-1] + sorted(classes)
        table: dict[tuple, int] = {}
        for row in gauge_rows:
            point = Point(row["lon"], row["lat"])
            level = max([key for key in sorted(classes) if classes[key].contains(point)], default=-1)
            table[(row["band"], level)] = table.get((row["band"], level), 0) + 1
        header = "  ".join(f"D{level}" if level >= 0 else "none" for level in levels)
        print("%-28s %s" % ("", header))
        for band in (
            "much below normal (<p10)",
            "below normal (p10-p25)",
            "normal (p25-p75)",
            "above normal (>p75)",
        ):
            print("%-28s %s" % (band, "  ".join("%4d" % table.get((band, level), 0) for level in levels)))

    measure_drought_layer(line, classes, miles)
    return miles


def measure_class_overlap(classes):
    """Are the U.S. Drought Monitor's classes nested, or mutually exclusive?

    Worth measuring rather than reading, because the widely-repeated answer is
    the wrong one for this endpoint. USDM's shapefiles are usually described
    as nested - D0 containing D1 containing D2 - and `export_drought.py` was
    first written to subtract each class from the one below on that basis.
    The GeoJSON at droughtmonitor.unl.edu/data/json/ does not do that: every
    pair intersects in zero area.

    It matters twice over. Nested classes drawn as translucent fills paint the
    worst areas darkest by stacking rather than by severity, and a per-class
    mileage read as "this class or worse" is wrong by the sum of everything
    inside it - 511 trail miles on the 2026-08-11 release, which is how this
    function came to exist.
    """
    from shapely.ops import unary_union

    levels = sorted(classes)
    print("\nU.S. Drought Monitor class overlap (0 everywhere means the classes are disjoint):")
    worst = 0.0
    for index, level in enumerate(levels):
        for other in levels[index + 1 :]:
            overlap = classes[level].intersection(classes[other]).area
            worst = max(worst, overlap)
            print("  D%d n D%d = %.6f sq deg" % (level, other, overlap))
    union_area = sum(classes[level].area for level in levels)
    combined = unary_union([classes[level] for level in levels]).area
    print("  sum of class areas %.3f vs area of their union %.3f" % (union_area, combined))
    print("  -> classes are %s" % ("DISJOINT" if worst == 0.0 else "OVERLAPPING"))


def measure_drought_layer(line, classes, national_miles):
    """What a shippable corridor-clipped drought layer costs, and what it loses.

    The national file is tens of megabytes because each class is one enormous
    multipolygon, which makes it look unshippable. Clipped to the corridor it
    is a few tens of kilobytes - but a clip is only worth quoting alongside
    proof that it did not move the boundaries, so this re-measures the trail
    against the clipped polygons and prints the difference rather than
    asserting there is none.
    """
    from shapely.geometry import mapping

    # The same three steps export_drought.py builds its corridor from, so the
    # size printed here is the size of the artifact that actually ships rather
    # than of a research-time approximation of it. Simplify, buffer, smooth:
    # the first makes the buffer affordable, the third is the biggest lever on
    # the bytes, and both are safe because the corridor edge is a 10 km choice
    # of ours rather than a boundary in anybody's data.
    corridor = line.simplify(CORRIDOR_SIMPLIFY_DEG).buffer(CORRIDOR_BUFFER_DEG).simplify(CORRIDOR_SMOOTH_DEG)
    clipped, features = {}, []
    for level in sorted(classes):
        piece = classes[level].intersection(corridor)
        if piece.is_empty:
            continue
        clipped[level] = piece
        features.append({"type": "Feature", "properties": {"DM": level}, "geometry": mapping(piece)})

    raw = json.dumps({"type": "FeatureCollection", "features": features}).encode()
    print(f"\nthe clipped drought GEOMETRY (+-{CORRIDOR_BUFFER_DEG * 111:.0f} km corridor):")
    print(f"  {len(raw)} bytes raw, {len(gzip.compress(raw))} bytes gzipped")
    # Compact, and carrying only `DM`. The shipped artifact is larger because
    # export_drought.py pretty-prints it and adds a label and trail miles per
    # band - 108,695 bytes / 14,507 gzipped on this release. This number is
    # the geometry's own cost; that one is what a hiker downloads.
    print("  re-measuring the trail against the clipped polygons:")
    for level, piece in clipped.items():
        pieces = piece_lines(line.intersection(piece))
        here = trail_miles(pieces)
        print(
            "    D%d  clipped %7.1f mi   national %7.1f mi   delta %+.3f"
            % (level, here, national_miles[level], here - national_miles[level])
        )


def piece_lines(geometry):
    pieces = [geometry] if geometry.geom_type == "LineString" else list(getattr(geometry, "geoms", []))
    return [list(p.coords) for p in pieces if p.geom_type == "LineString"]


def main():
    print(f"Water-conditions sources, measured {datetime.date.today().isoformat()}\n")
    parts = fetch_centerline_parts()
    index = TrailIndex(parts)
    gauges = measure_gauges(index)
    measure_wells(index)
    sample_nwm(parts)
    measure_nwm_retrospective_cost(parts)
    measure_drought(parts, gauges)


if __name__ == "__main__":
    main()
