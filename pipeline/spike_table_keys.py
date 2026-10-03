"""Spike: find the smallest set of current values that is unique, for the registry tables with no unique key.

Usage: python spike_table_keys.py   (from pipeline/; reads sources.json live)

A spike for decision 40 of #1793 — Rebuild the data platform as dlt → dbt:
seven contracted marts, a monthly refresh, published docs, and lighter phone
downloads (pipeline/ELT.md, "One key per table"). It is what measured the
thirteen keys that table marks as measured on 2026-10-01; it is not on any
publish path and has no tests. Rerun it to check a key before a staging model
relies on it.

For each layer it reads every row's attributes and full geometry (every vertex
at 6 decimal places, about 0.1 m) with lib/user_agent.py's agent, then reports:
  - exact copies: rows equal on every column but the server's own row ids
    (OBJECTID, FID, GlobalID on a reloaded layer), which staging's dedupe removes;
  - duplicates on the key the morning's incremental research named, and what
    differs inside each group;
  - after the exact copies are gone, the smallest unique combination: single
    columns first, then pairs, then a column plus position, never a row id.
Rows are cached, and results written, under data/spike_table_keys/ (gitignored).
The greedy search ELT.md quotes for blm_trails, and the per-candidate counts
for the other twelve, were run over that cache by hand on the same day.
"""

import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path

import requests

from lib.http_retry import request_with_retry
from lib.user_agent import USER_AGENT

OUT_DIR = Path(__file__).parent / "data" / "spike_table_keys"
OUT = OUT_DIR / "results.json"
S = requests.Session()
S.headers["User-Agent"] = USER_AGENT

ARCGIS = {
    "dec_primitive_campsites": "ASSET_UID",
    "dec_parking_areas": "ASSET_UID",
    "dec_backcountry_features": "ASSET_UID",
    "oprhp_trail_closures": None,
    "nynjtc_long_path": None,
    "blm_trails": None,
    "alaska_trails": None,
    "cdtc_centerline": "STATE",
    "ct_deep_blue_blazed": None,
    "nc_mst_trail": None,
}
SOCRATA = {"nyc_parks_trails": None, "nyc_public_restrooms": None, "nyc_dot_greenways": "segmentid"}
ROW_IDS = {
    "objectid",
    "fid",
    "oid",
    "globalid",
    "shape_length",
    "shape__length",
    "shape_area",
    "shape__area",
    "shape.len",
    "shape.stlength()",
    ":id",
}


def r5(v):
    try:
        return round(float(v), 5)
    except (TypeError, ValueError):
        return None


def ends(geometry):
    if not geometry:
        return None
    if "x" in geometry:
        return (r5(geometry["x"]), r5(geometry["y"]))
    paths = geometry.get("paths") or geometry.get("rings")
    if paths:
        first, last = paths[0][0], paths[-1][-1]
        return (r5(first[0]), r5(first[1]), r5(last[0]), r5(last[1]))
    coords = geometry.get("coordinates")
    if coords:
        flat = coords
        while isinstance(flat[0], list) and isinstance(flat[0][0], list):
            flat = flat[0]
        if not isinstance(flat[0], list):
            return (r5(flat[0]), r5(flat[1]))
        return (r5(flat[0][0]), r5(flat[0][1]), r5(flat[-1][0]), r5(flat[-1][1]))
    return None


def geom_hash(geometry):
    """Every vertex, rounded to 6 decimal places: equal only when the whole shape is."""
    if not geometry:
        return None

    def rounded(v):
        if isinstance(v, list):
            return [rounded(x) for x in v]
        if isinstance(v, (int, float, str)):
            try:
                return round(float(v), 6)
            except ValueError:
                return v
        return v

    body = {k: rounded(v) for k, v in geometry.items() if k in ("x", "y", "paths", "rings", "points", "coordinates")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]


def arcgis_rows(url):
    meta = request_with_retry(url, session=S, params={"f": "json"}, timeout=60).json()
    rows, offset, size = [], 0, 1000
    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "outSR": 4326,
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": size,
        }
        params["geometryPrecision"] = 6  # every vertex at about 0.1 m, so two lines that differ anywhere hash apart
        resp = request_with_retry(url.rstrip("/") + "/query", session=S, params=params, timeout=120)
        try:
            body = resp.json()
        except ValueError:
            body = {"error": {"message": "not json"}}
        if "error" in body:
            if size == 1:
                raise RuntimeError(body["error"])
            size //= 2
            continue
        batch = body.get("features") or []
        if not batch:
            break
        for f in batch:
            g = f.get("geometry")
            rows.append({**(f.get("attributes") or {}), "__pos": ends(g), "__geom": geom_hash(g)})
        offset += len(batch)
    return rows, [f["name"] for f in meta.get("fields", [])]


def socrata_rows(entry):
    url = f"https://{entry['domain']}/resource/{entry['dataset_id']}.json"
    rows, offset = [], 0
    where = entry.get("where")
    while True:
        params = {"$limit": 5000, "$offset": offset, "$order": ":id", "$select": ":*, *"}
        if where:
            params["$where"] = where
        batch = request_with_retry(url, session=S, params=params, timeout=120).json()
        if not batch:
            break
        for r in batch:
            geom = next((v for k, v in r.items() if isinstance(v, dict) and "coordinates" in v), None)
            rows.append(
                {
                    k: (json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v)
                    for k, v in r.items()
                    if not (isinstance(v, dict) and "coordinates" in v)
                }
                | {"__pos": ends(geom), "__geom": geom_hash(geom)}
            )
        offset += len(batch)
    fields = sorted({k for r in rows for k in r if k != "__pos"})
    return rows, fields


def distinct(rows, cols):
    return len({tuple(json.dumps(r.get(c), sort_keys=True, default=str) for c in cols) for r in rows})


def signature(row, candidates):
    return json.dumps([row.get(c) for c in candidates] + [row.get("__geom")], default=str)


def analyse(key, rows, fields, named):
    candidates = [f for f in fields if f.lower() not in ROW_IDS and not f.startswith(":")]
    # True duplicates: equal on every column but the server's own row ids, and on position.
    # No combination of current values can tell them apart; staging dedupe is what removes them.
    signatures = Counter(signature(r, candidates) for r in rows)
    true_dupe_rows = sum(c - 1 for c in signatures.values() if c > 1)
    seen, deduped = set(), []
    for r in rows:
        sig = signature(r, candidates)
        if sig not in seen:
            seen.add(sig)
            deduped.append(r)
    report = {"rows": len(rows), "named": named, "true_duplicate_rows": true_dupe_rows, "rows_after_dedupe": len(deduped)}
    rows = deduped
    n = len(rows)
    nulls = {f: sum(r.get(f) is None for r in rows) for f in candidates}
    usable = candidates  # nullable columns may sit in a key; their null count is reported beside it
    if named:
        counts = Counter(r.get(named) for r in rows)
        dupes = {k: c for k, c in counts.items() if c > 1}
        report["named_distinct"] = len(counts)
        report["named_nulls"] = counts.get(None, 0)
        groups = []
        for value in list(dupes)[:40]:
            members = [r for r in rows if r.get(named) == value]
            same = [f for f in candidates + ["__pos"] if len({json.dumps(m.get(f), default=str) for m in members}) == 1]
            differ = [f for f in candidates + ["__pos"] if f not in same]
            groups.append({"value": value, "rows": len(members), "differ_on": differ[:12]})
        report["duplicate_groups"] = groups
        report["true_duplicates"] = sum(1 for g in groups if not g["differ_on"])
    singles = sorted((f for f in usable if distinct(rows, [f]) == n), key=lambda f: (nulls[f], f))
    report["unique_single_fields"] = singles
    found = []
    if not singles:
        ranked = sorted(usable, key=lambda f: (-distinct(rows, [f]), nulls[f]))[:14]
        for a, b in itertools.combinations(ranked, 2):
            if distinct(rows, [a, b]) == n:
                found.append([a, b])
        if not found:
            for a in ranked[:10]:
                if distinct(rows, [a, "__pos"]) == n:
                    found.append([a, "__pos"])
            if distinct(rows, ["__pos"]) == n:
                found.append(["__pos"])
        if not found:
            for a, b, c in itertools.combinations(ranked[:10], 3):
                if distinct(rows, [a, b, c]) == n:
                    found.append([a, b, c])
                    if len(found) > 5:
                        break
        report["best_distinct"] = {f: distinct(rows, [f]) for f in ranked[:6]}
        report["pos_distinct"] = distinct(rows, ["__pos"])
    if not found and not singles:
        if distinct(rows, ["__geom"]) == n:
            found.append(["__geom"])
        else:
            top = sorted(usable, key=lambda f: (-distinct(rows, [f]), nulls[f]))[:1]
            cols = top + ["__geom"]
            groups = Counter(json.dumps([r.get(c) for c in cols], default=str) for r in rows)
            clash = [g for g, c in groups.items() if c > 1][:3]
            samples = []
            for g in clash:
                members = [r for r in rows if json.dumps([r.get(c) for c in cols], default=str) == g]
                differ = [f for f in candidates if len({json.dumps(m.get(f), default=str) for m in members}) > 1]
                samples.append({"on": cols, "rows": len(members), "differ_on": differ})
            report["collisions_after_dedupe"] = samples
            report["geom_distinct"] = distinct(rows, ["__geom"])
    report["unique_combinations"] = [{"columns": c, "nulls": {f: nulls.get(f) for f in c if f != "__pos"}} for c in found[:8]]
    report["unique_single_fields"] = [{"column": f, "nulls": nulls.get(f)} for f in singles]
    return report


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = {e["key"]: e for e in json.loads((Path(__file__).parent / "sources.json").read_text())["sources"]}
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    for key, named in {**ARCGIS, **SOCRATA}.items():
        if key in results:
            continue
        entry = registry[key]
        print(f"{key} ...", flush=True)
        cache = OUT_DIR / f"rows_{key}.json"
        try:
            if cache.exists():
                rows, fields = json.loads(cache.read_text())
            else:
                rows, fields = socrata_rows(entry) if key in SOCRATA else arcgis_rows(entry["url"])
                cache.write_text(json.dumps([rows, fields], default=str))
            results[key] = analyse(key, rows, fields, named)
            r = results[key]
            print(
                f"  {r['rows']} rows, {r['true_duplicate_rows']} true duplicates; singles {r['unique_single_fields'][:3]}; combos {r['unique_combinations'][:3]}"
            )
        except Exception as error:  # noqa: BLE001 - a probe reports and goes on
            results[key] = {"error": str(error)[:300]}
            print("  error", error)
        OUT.write_text(json.dumps(results, indent=1, default=str))


if __name__ == "__main__":
    main()
