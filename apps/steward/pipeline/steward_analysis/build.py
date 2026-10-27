"""Score every CSI site and write the two outputs.

    python -m steward_analysis.build --fetch     read the three layers, then score
    python -m steward_analysis.build             score what data/raw/ already holds

Writes, under data/out/ (gitignored, like everything under data/), two public files
that the web app will serve as static files beside itself (decided 2026-10-27,
PLAN.md §2g):

    summary.json   Counts by type, action, tier, crew size and club, plus the method and
                   its weights: the Analysis screen's whole input, and small (8 KB).
                   It carries no coordinates, miles or site ids, so the Analysis screen
                   never downloads the 3.7 MB below to draw a chart.
    sites.json     One record per site with its location and every score, sorted by
                   club and then by need. ATC publishes the same locations in its own
                   open layer; this file adds the scores.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from steward_analysis import rules, sources, spatial

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data"

#: The joining distance for complexes. `@unvalidated`: 200 ft sits near the
#: median gap from a site to its nearest neighbour (198 ft, measured
#: 2026-10-24), and that is all that chose it. What would settle it: a club's
#: own judgement, for a handful of complexes it knows, of which sites belong
#: together (PLAN.md §2a).
COMPLEX_JOIN_FT = 200

#: The CSI fields the rules read. A row missing any of them gets the action
#: "unknown" and is counted in the summary rather than guessed at.
RULE_FIELDS = (
    "CSI_Score",
    "Size_ft2",
    "Proximity_Water_ft",
    "Proximity_AT_ft",
    "Median_Percent_Slope_Footprint",
    *rules.CSI_WEIGHTS,
)


#: Directions from the trail are given only when the job's own distance agrees
#: with ATC's `Proximity_AT_ft` to within this many feet, or within half of
#: ATC's figure for a site far from the trail. Measured 2026-10-27: the two
#: agree to a median of 12 ft, and 3,414 of 3,442 sites within 50 ft. All 28
#: of the rest are in Georgia, where ATC puts the site on or beside the trail
#: and ATC's centerline has no trail for miles (up to 24,770 ft), as if it were
#: measured from a trail that layer leaves out. Directions that would send a
#: volunteer miles the wrong way are worse than none, so those sites get none.
#: `@unvalidated`: 100 ft was picked to sit clear of the 50 ft that covers
#: nearly every site; what would settle it is learning which trail ATC measured
#: those Georgia sites against.
TRAIL_AGREEMENT_FT = 100


def _trail_agrees(found: dict | None, atc_ft) -> bool:
    if found is None or atc_ft is None or pd.isna(atc_ft):
        return False
    return abs(found["ft"] - float(atc_ft)) <= max(TRAIL_AGREEMENT_FT, 0.5 * float(atc_ft))


class SchemaError(RuntimeError):
    pass


def load_raw(raw_dir: Path) -> tuple[dict, dict, dict, dict]:
    csi = json.loads((raw_dir / "csi.json").read_text())
    parking = json.loads((raw_dir / "parking.geojson").read_text())
    padus = json.loads((raw_dir / "padus.geojson").read_text())
    # Optional, so a raw directory fetched before the centerline was added still scores.
    centerline_path = raw_dir / "centerline.geojson"
    centerline = json.loads(centerline_path.read_text()) if centerline_path.exists() else {"features": []}
    return csi, parking, padus, centerline


def check_schema(rows: list[dict]) -> None:
    """Refuse to score a layer that has lost a field the rules read, rather than score it wrongly."""
    if not rows:
        raise SchemaError("the CSI layer came back empty")
    missing = [f for f in sources.CSI_FIELDS if f not in rows[0]]
    if missing:
        raise SchemaError(f"the CSI layer no longer has {missing}; the rules in rules.py read them")


def score(
    csi_rows: list[dict],
    parking: dict,
    padus: dict,
    camping_rules: dict[str, bool] | None = None,
    centerline: dict | None = None,
) -> pd.DataFrame:
    """One row per CSI site with a location, carrying every derived column.

    `camping_rules` maps a PAD-US unit name to whether a REVIEWED rule restricts
    dispersed camping there. It is empty until the hand-transcribed table exists
    (PLAN.md §2e), and only it, never `rules.regime_guess`, can add the
    restricted-camping points to a site's need.
    """
    camping_rules = camping_rules or {}
    df = pd.DataFrame([r for r in csi_rows if r.get("Latitude") is not None and r.get("Longitude") is not None])
    df = df.reset_index(drop=True)
    df["Site_Type"] = df["Site_Type"].fillna("").str.strip()
    df["Inventory_Status"] = df["Inventory_Status"].fillna("").str.strip()
    df["complete"] = df[list(RULE_FIELDS)].notna().all(axis=1)

    ids = spatial.complexes(df["Latitude"], df["Longitude"], COMPLEX_JOIN_FT)
    df["complex_n"] = ids
    df["complex_size"] = df.groupby("complex_n")["OBJECTID"].transform("count")
    # A complex id that survives a re-run: its alphabetically first member's RIMS_ID.
    first_member = df.groupby("complex_n")["RIMS_ID"].transform(lambda s: sorted(str(v) for v in s)[0])
    df["complex_id"] = "cx-" + first_member.str[:8]

    points = [f for f in parking.get("features", []) if f.get("geometry")]
    if points:
        idx, feet = spatial.nearest(
            df["Latitude"],
            df["Longitude"],
            [p["geometry"]["coordinates"][1] for p in points],
            [p["geometry"]["coordinates"][0] for p in points],
        )
        df["parking_name"] = [points[i]["properties"].get("Name") for i in idx]
        df["parking_mi"] = (feet / spatial.FEET_PER_MILE).round(2)
    else:
        df["parking_name"] = None
        df["parking_mi"] = None

    found = spatial.from_trail(df["Latitude"], df["Longitude"], (centerline or {}).get("features", []))
    df["from_trail"] = [f if _trail_agrees(f, atc_ft) else None for f, atc_ft in zip(found, df["Proximity_AT_ft"])]
    df["from_trail_withheld"] = [f is not None and kept is None for f, kept in zip(found, df["from_trail"])]

    units = [spatial.most_specific(u) for u in spatial.land_units(df["Latitude"], df["Longitude"], padus.get("features", []))]
    df["unit_manager"] = [u.get("Mang_Name") if u else None for u in units]
    df["unit_designation"] = [u.get("Des_Tp") if u else None for u in units]
    df["unit_name"] = [u.get("Unit_Nm") if u else None for u in units]
    df["unit_state"] = [u.get("State_Nm") if u else None for u in units]
    df["regime_guess"] = [
        rules.regime_guess(m, d, n) for m, d, n in zip(df["unit_manager"], df["unit_designation"], df["unit_name"])
    ]
    df["regime_reviewed"] = df["unit_name"].map(lambda n: camping_rules.get(n) if n else None)

    actions, needs, parts, tiers, crews = [], [], [], [], []
    for row in df.itertuples(index=False):
        if not row.complete:
            actions.append(rules.UNKNOWN)
            needs.append(0)
            parts.append(None)
            tiers.append(None)
            crews.append(None)
            continue
        facts = rules.SiteFacts(
            site_type=row.Site_Type,
            inventory_status=row.Inventory_Status,
            csi=int(row.CSI_Score),
            size_ft2=float(row.Size_ft2),
            water_ft=float(row.Proximity_Water_ft),
            trail_ft=float(row.Proximity_AT_ft),
            slope_footprint_pct=float(row.Median_Percent_Slope_Footprint),
            complex_size=int(row.complex_size),
            camping_restricted=_reviewed_restricted(row.regime_reviewed),
        )
        a = rules.action(facts)
        p = rules.need_parts(facts)
        n = rules.need_from_parts(p)
        actions.append(a)
        needs.append(n)
        parts.append(p)
        tiers.append(rules.tier(n, a))
        crews.append(rules.crew(facts, a))
    df["action"] = actions
    df["need"] = needs
    df["need_parts"] = parts
    df["tier"] = tiers
    df["crew"] = crews
    return df


def _reviewed_restricted(value) -> bool:
    """True only for a reviewed rule that restricts camping; a missing rule is not a restriction."""
    return value is not None and not pd.isna(value) and bool(value)


def csi_reproduction(df: pd.DataFrame) -> tuple[int, int]:
    """How many complete rows' published CSI equals the reconstructed formula's (PLAN.md §1)."""
    complete = df[df["complete"]]
    matches = sum(rules.csi_from_indicators(r) == int(r["CSI_Score"]) for r in complete.to_dict("records"))
    return matches, len(complete)


def summarize(df: pd.DataFrame, data_last_edit_ms: int | None, skipped_no_location: int) -> dict:
    """The public summary. Counts only: see the module docstring."""
    con = duckdb.connect()
    con.register("sites", df[["Site_Type", "Trail_Club", "action", "tier", "crew", "complex_n", "regime_guess"]])

    def pairs(sql: str) -> dict:
        return {k if k is not None else "(none)": v for k, v in con.sql(sql).fetchall()}

    by_tier = con.sql(
        """
        SELECT tier,
               count(*) FILTER (WHERE crew = 'one_person') AS one_person,
               count(*) FILTER (WHERE crew = 'team')       AS team,
               count(*) FILTER (WHERE crew = 'crew')       AS crew,
               count(*)                                    AS total
        FROM sites WHERE tier IS NOT NULL
        GROUP BY tier ORDER BY tier
        """
    ).fetchall()
    clubs = con.sql(
        """
        SELECT Trail_Club AS club,
               count(*)                                     AS sites,
               count(*) FILTER (WHERE tier IS NOT NULL)     AS actionable,
               count(*) FILTER (WHERE tier = 'P1')          AS p1,
               count(*) FILTER (WHERE tier = 'P2')          AS p2,
               count(*) FILTER (WHERE tier = 'P3')          AS p3,
               count(*) FILTER (WHERE crew = 'one_person')  AS one_person,
               count(*) FILTER (WHERE crew = 'team')        AS team,
               count(*) FILTER (WHERE crew = 'crew')        AS crew
        FROM sites
        GROUP BY Trail_Club
        ORDER BY p1 DESC, p2 DESC, club
        """
    ).df()
    complexes = con.sql(
        """
        WITH c AS (SELECT complex_n, count(*) AS n FROM sites GROUP BY complex_n)
        SELECT count(*), count(*) FILTER (WHERE n >= 2), count(*) FILTER (WHERE n >= 4), max(n) FROM c
        """
    ).fetchone()
    matches, complete = csi_reproduction(df)
    edited = datetime.fromtimestamp(data_last_edit_ms / 1000, UTC).date().isoformat() if data_last_edit_ms else None
    weights = rules.DEFAULT_WEIGHTS
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": {
            "layer": sources.CSI_LAYER,
            "data_last_edited": edited,
            "sites": len(df),
            "skipped_no_location": skipped_no_location,
        },
        "csi_formula": {"reproduces": matches, "of": complete, "incomplete_rows": int((~df["complete"]).sum())},
        "sites_by_type": pairs("SELECT nullif(Site_Type, '') AS t, count(*) FROM sites GROUP BY t ORDER BY 2 DESC"),
        "actions": pairs("SELECT action, count(*) FROM sites GROUP BY action ORDER BY 2 DESC"),
        "priority_by_crew": [dict(zip(("tier", "one_person", "team", "crew", "total"), row)) for row in by_tier],
        "from_trail": {
            "given": int(df["from_trail"].notna().sum()),
            "withheld_disagreeing_with_atc": int(df["from_trail_withheld"].sum()),
            "agreement_ft": TRAIL_AGREEMENT_FT,
        },
        "complexes": {
            "join_ft": COMPLEX_JOIN_FT,
            "count": complexes[0],
            "with_2_plus": complexes[1],
            "with_4_plus": complexes[2],
            "largest": complexes[3],
        },
        "clubs": clubs.to_dict("records"),
        "camping_rules": {
            "reviewed_units": int(df.loc[df["regime_reviewed"].notna(), "unit_name"].nunique()),
            "sites_with_reviewed_rule": int(df["regime_reviewed"].notna().sum()),
            "status": "pending review: the restricted-camping weight adds nothing until a reviewed rule exists",
            "guesses": pairs("SELECT regime_guess, count(*) FROM sites GROUP BY regime_guess ORDER BY 2 DESC"),
        },
        "method": {
            "weights": {
                "deficit": weights.deficit,
                "water": weights.water,
                "trail": weights.trail,
                "cluster": weights.cluster,
                "restricted": weights.restricted,
            },
            "tiers": {"P1_min": rules.P1_MIN, "P2_min": rules.P2_MIN},
            "work_csi_max": rules.WORK_CSI_MAX,
            "close_water_ft": rules.CLOSE_WATER_FT,
            "adopt_csi_min": rules.ADOPT_CSI_MIN,
            "one_person_max_ft2": rules.ONE_PERSON_MAX_FT2,
            "crew_min_ft2": rules.CREW_MIN_FT2,
            "csi_weights": rules.CSI_WEIGHTS,
        },
    }


def _none(value):
    """pandas' NaN, which a missing tier, crew or name becomes in a DataFrame, as JSON's null."""
    return None if value is None or (not isinstance(value, (str, bool)) and pd.isna(value)) else value


def _num(value, digits: int):
    return None if value is None or pd.isna(value) else round(float(value), digits)


def site_records(df: pd.DataFrame) -> list[dict]:
    """sites.json's contents: every site, grouped by club, highest need first within each."""
    out: list[dict] = []
    ordered = df.assign(_club=df["Trail_Club"].fillna("")).sort_values(
        ["_club", "need", "RIMS_ID"], ascending=[True, False, True]
    )
    for row in ordered.to_dict("records"):
        documented = [d.strip() for d in (row.get("Documented") or "").split(",") if d.strip()]
        out.append(
            {
                "rims_id": row["RIMS_ID"],
                "global_id": row["GlobalID"],
                "name": _none(row.get("Location")),
                "club": _none(row.get("Trail_Club")),
                "region": _none(row.get("Region")),
                "site_type": row["Site_Type"] or None,
                "inventory_status": row["Inventory_Status"] or None,
                "documented_in": documented,
                "lat": _num(row["Latitude"], 5),
                "lon": _num(row["Longitude"], 5),
                "mile": _num(row.get("AT_Mile_2026"), 1),
                "csi": None if pd.isna(row["CSI_Score"]) else int(row["CSI_Score"]),
                "indicators": {f: None if pd.isna(row[f]) else int(row[f]) for f in rules.CSI_WEIGHTS},
                "size_ft2": _num(row["Size_ft2"], 0),
                "water_ft": _num(row["Proximity_Water_ft"], 0),
                "water_ft_source": _none(row.get("Nearest_Water_Source")),
                "trail_ft": _num(row["Proximity_AT_ft"], 0),
                "nearest_site_ft": _num(row.get("Proximity_Other_Site_ft"), 0),
                "slope_footprint_pct": _num(row["Median_Percent_Slope_Footprint"], 1),
                "complex_id": row["complex_id"],
                "complex_size": int(row["complex_size"]),
                "nearest_parking": {"name": _none(row["parking_name"]), "mi": _num(row["parking_mi"], 2)},
                # Where to leave the A.T. and which way to walk: the nearest point on ATC's
                # centerline, the distance from it and the bearing from it to the site.
                "from_trail": _trail(row["from_trail"]),
                "land_unit": {
                    "manager": _none(row["unit_manager"]),
                    "designation": _none(row["unit_designation"]),
                    "name": _none(row["unit_name"]),
                    "state": _none(row["unit_state"]),
                },
                "camping": (
                    {"restricted": bool(row["regime_reviewed"]), "source": "reviewed"}
                    if row["regime_reviewed"] is not None and not pd.isna(row["regime_reviewed"])
                    else {"regime": row["regime_guess"], "source": "guess"}
                ),
                "need": int(row["need"]),
                # What each of the five weights multiplies for this site, so a club's own
                # weights re-rank it as sum(weight x part) (rules.need_parts). None where
                # the site's assessment is incomplete and it has no need to re-rank.
                "need_parts": _parts(row["need_parts"]),
                "tier": _none(row["tier"]),
                "action": _none(row["action"]),
                "crew": _none(row["crew"]),
            }
        )
    return out


def _parts(parts: dict | None) -> dict | None:
    if not isinstance(parts, dict):
        return None
    # Not rounded. The deficit part is k/27, and any rounding of it can tip a
    # weighted sum that lands on exactly .5 to the other side; written in full,
    # the web app's sum (in rules.WEIGHT_NAMES order) is the same double this
    # one is, and rounds the same way.
    return {name: float(parts[name]) for name in rules.WEIGHT_NAMES}


def _trail(found: dict | None) -> dict | None:
    if not found:
        return None
    return {
        "lat": round(found["lat"], 5),
        "lon": round(found["lon"], 5),
        "ft": round(found["ft"]),
        "bearing_deg": round(found["bearing_deg"]),
        "toward": found["toward"],
    }


def _plain(value):
    """numpy scalars, which DuckDB and pandas hand back, as the Python numbers json can write."""
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def write_outputs(out_dir: Path, summary: dict, sites: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=_plain, allow_nan=False) + "\n")
    # Compact: this is the file a phone downloads, and indentation alone would be a third of it.
    (out_dir / "sites.json").write_text(json.dumps(sites, separators=(",", ":"), default=_plain, allow_nan=False) + "\n")


def run(data_dir: Path, fetch: bool = False) -> dict:
    raw_dir, out_dir = data_dir / "raw", data_dir / "out"
    if fetch:
        from steward_analysis.fetch import fetch_all

        fetch_all(raw_dir)
    csi, parking, padus, centerline = load_raw(raw_dir)
    check_schema(csi["rows"])
    df = score(csi["rows"], parking, padus, centerline=centerline)
    skipped = len(csi["rows"]) - len(df)
    summary = summarize(df, csi.get("data_last_edit_ms"), skipped)
    write_outputs(out_dir, summary, site_records(df))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fetch", action="store_true", help="read the three layers into data/raw/ first")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="the data directory (default: %(default)s)")
    args = parser.parse_args(argv)
    summary = run(args.data, fetch=args.fetch)
    tiers = {row["tier"]: row["total"] for row in summary["priority_by_crew"]}
    formula = summary["csi_formula"]
    print(
        f"{summary['source']['sites']} sites · actionable {sum(tiers.values())} "
        f"(P1 {tiers.get('P1', 0)}, P2 {tiers.get('P2', 0)}, P3 {tiers.get('P3', 0)}) · "
        f"CSI formula reproduces {formula['reproduces']} of {formula['of']} · written to {args.data / 'out'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
