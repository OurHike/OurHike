"""new_data_report: decision 31's review of what parity cannot check, read from a built warehouse.

    python new_data_report.py --warehouse data/warehouse.duckdb --out <dir> [--parity-dir <dir>]

Parity (parity.py, gate_report.py) holds every key today's pipeline publishes
to today's exporter. It cannot check a row today's exporters never wrote, so
decision 31 ("publish new data in this PR", pipeline/ELT.md, "The go/no-go
gate") adds a review of what the new marts carry. This writes
`new_data_report.md`, for a maintainer reading a pull request, and
`new_data_report.json`, with:

1. rows per org × type × mart: every table in the warehouse's `marts` schema,
   counted by its `club` and by the column MART_TYPES names for it;
2. the licence basis and `may_publish` of every layer, from
   `int_sources__publication` (ELT.md, "Who may publish"), with the `sources`
   mart's steward, title and kind beside it and the layer's rows in each mart;
3. every closure, warning, water and shelter source the marts carry, one line
   each, and whether today's files carry rows from it: read from parity.py's
   results (`--parity-dir`, the `<family>.json` files `--json-dir` writes),
   whose `old_sources` count the records today's exporter wrote on the same
   input by the source each names. Without `--parity-dir` the answer is "not
   measured".

WHAT IT NEVER HOLDS, and how that is made true rather than hoped for:
- no person field. Every query names its columns (never `select *`), none of
  them a row's free text, and the document is refused before it is written
  if any field in it is named in extract/_kinds.py's PERSON_FIELDS (the
  denylist, read with `ast` so this needs none of the extract's imports);
- no location at all, so no dispersed campsite's: counts, source keys and
  registry fields only, and the same refusal for any field named in
  LOCATION_FIELDS. CLAUDE.md, "Show what you changed", lists "a dispersed
  campsite at a readable zoom" among what must never be published, and a
  coordinate in a report is that location at any zoom.

Map shot recipes (decision 31's third item) are not here; the report's last
section says what a recipe per region would need.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
REPORT_FORMAT = "ourhike-new-data-report/1"
PARITY_RESULT_FORMAT = "ourhike-parity-result/1"  # parity.RESULT_FORMAT; tests hold the two equal

#: The column each mart's rows are typed by, for the org × type × mart counts.
#: A mart not named here is counted by club alone, and says so.
MART_TYPES = {
    "trail_lines": "line_kind",
    "points_of_interest": "poi_type",
    "elevation": "line_id",
    "closures": "notice_kind",
    "warnings": "warning_kind",
    "places": "kind",
    "sources": "kind",
    "challenges": None,
    "trail_network": None,
    "podcasts": None,
    "suggested_hikes": None,
}

#: Where each kind of new source is read from: (mart, the line's label, how a
#: phone file names the source, the column typing the line, the rows it
#: covers, the columns all of that needs). The name is the one
#: parity.SOURCE_FIELDS finds on today's records: a POI's `source` (atc_csi),
#: a notice's `source_key` (atc_trail_updates), a closed line's
#: `closure_source`, or the line's own source where its own status field
#: closed it (export_nearby_trails.py writes no closure_source then).
NEW_SOURCE_QUERIES = (
    ("closures", "closure", "source_key", "notice_kind", "true", ("source_key", "notice_kind")),
    (
        "trail_lines",
        "closure",
        "coalesce(closure_source, source_key)",
        "closure_kind",
        "closure_kind is not null",
        ("source_key", "closure_source", "closure_kind"),
    ),
    ("warnings", "warning", "source_key", "warning_kind", "true", ("source_key", "warning_kind")),
    (
        "points_of_interest",
        "water",
        "source",
        "poi_type",
        "poi_type = 'water' and retired is null",
        ("source_key", "source", "poi_type", "retired"),
    ),
    (
        "points_of_interest",
        "shelter",
        "source",
        "poi_type",
        "poi_type = 'shelter' and retired is null",
        ("source_key", "source", "poi_type", "retired"),
    ),
)

#: Fields that place a row on the ground. The report holds none of them.
LOCATION_FIELDS = frozenset(
    {
        "lat",
        "lon",
        "latitude",
        "longitude",
        "geom",
        "geometry",
        "geom_geojson",
        "coordinates",
        "bbox",
        "start_lat",
        "start_lon",
        "end_lat",
        "end_lon",
    }
)

MAP_SHOTS = (
    "Not in this report: map shot recipes are their own piece of work. A recipe per region would need: "
    "a region, read from `reference/trail_orgs.json`'s `states` for the clubs whose rows are new; a camera "
    "the region fits at a zoom where no campsite is readable, because CLAUDE.md's four rules forbid a dispersed "
    "campsite at a readable zoom; UA's data, which the preview camera has (`pr-preview.yml`), never a fixture "
    "that looks real; no signed-in account, nobody's reports or photos and no location fix; and a client that "
    "draws the new rows, which v1's files do not carry yet (decision 44). Each recipe lives in "
    "`client/preview-shots/`, under `.claude/skills/pr-screenshot/SKILL.md`'s contract."
)


def person_fields() -> frozenset[str]:
    """extract/_kinds.py's PERSON_FIELDS, read out of its source: the one denylist, without its module's imports."""
    tree = ast.parse((PIPELINE_DIR / "extract" / "_kinds.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PERSON_FIELDS" for t in node.targets):
            names = [
                part.value.lower()
                for part in ast.walk(node.value)
                if isinstance(part, ast.Constant) and isinstance(part.value, str)
            ]
            if names:
                return frozenset(names)
    raise RuntimeError("extract/_kinds.py has no PERSON_FIELDS this can read, so the report cannot check itself")


def refuse_what_it_must_not_hold(document, denied_people: frozenset[str], path: str = "") -> None:
    """Raise if any field in `document` is a person field or a location field, naming where."""
    if isinstance(document, dict):
        for name, value in document.items():
            lowered = str(name).lower()
            if lowered in denied_people:
                raise ValueError(f"{path}{name}: a person field (extract/_kinds.py PERSON_FIELDS) is never in this report")
            if lowered in LOCATION_FIELDS:
                raise ValueError(f"{path}{name}: a location is never in this report (no dispersed campsite's, no anybody's)")
            refuse_what_it_must_not_hold(value, denied_people, f"{path}{name}.")
    elif isinstance(document, list):
        for index, value in enumerate(document):
            refuse_what_it_must_not_hold(value, denied_people, f"{path}{index}.")


def _tables(con) -> dict[tuple[str, str], set[str]]:
    """{(schema, table): its columns}, for every table and view in the warehouse, a mart's versions aside.

    A versioned mart (decision 44) is a table per version, `closures_v1`, and
    a view under the mart's own name over the latest; counting both would
    count each row twice, so a `<mart>_v<n>` beside a `<mart>` is left out
    and the mart is counted under its own name."""
    found: dict[tuple[str, str], set[str]] = {}
    for schema, table, column in con.execute(
        "select table_schema, table_name, column_name from information_schema.columns order by all"
    ).fetchall():
        found.setdefault((schema, table), set()).add(column)
    versions = {key for key in found if re.fullmatch(r".+_v\d+", key[1]) and (key[0], re.sub(r"_v\d+$", "", key[1])) in found}
    return {key: columns for key, columns in found.items() if key not in versions}


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def mart_counts(con, tables: dict) -> list[dict]:
    """Rows per (mart, club, type), for every table in the `marts` schema."""
    rows: list[dict] = []
    for (schema, mart), columns in sorted(tables.items()):
        if schema != "marts":
            continue
        club = _quote("club") if "club" in columns else "null"
        typed = MART_TYPES.get(mart)
        kind = f"cast({_quote(typed)} as varchar)" if typed and typed in columns else "null"
        if mart == "points_of_interest" and "retired" in columns:
            kind = f"{kind} || case when retired is not null then ' (retired tombstone)' else '' end"
        query = f"select {club} as club, {kind} as kind, count(*) from marts.{_quote(mart)} group by all order by all"
        # An empty mart is a line of its own: no rows is a finding a reviewer
        # should see, not an absence they have to notice.
        for club_value, kind_value, count in con.execute(query).fetchall() or [(None, None, 0)]:
            rows.append(
                {
                    "mart": mart,
                    "club": club_value if "club" in columns else None,
                    "type_column": typed if typed and typed in columns else None,
                    "type": kind_value,
                    "rows": count,
                }
            )
    return rows


def layers(con, tables: dict) -> list[dict]:
    """int_sources__publication's every row, with the sources mart's registry fields and the layer's rows per mart."""
    publication = next((key for key in tables if key[1] == "int_sources__publication"), None)
    if publication is None:
        raise ValueError("the warehouse has no int_sources__publication, so no layer's licence or may_publish can be read")
    schema = _quote(publication[0])
    sources = ("marts", "sources") in tables
    registry = (
        "left join marts.sources as registry on registry.source_key = publication.source_key"
        if sources
        else "left join (select null as source_key) as registry on false"
    )
    fields = (
        "registry.steward, registry.provider, registry.title, registry.kind, registry.reaches_hikers"
        if sources
        else "null, null, null, null, null"
    )
    query = f"""
        select publication.source_key, publication.licence_basis, publication.may_publish, publication.publication_rule,
               {fields}
        from {schema}.int_sources__publication as publication
        {registry}
        order by publication.source_key
    """
    per_mart: dict[str, dict[str, int]] = {}
    for (mart_schema, mart), columns in sorted(tables.items()):
        if mart_schema != "marts" or mart == "sources" or "source_key" not in columns:
            continue
        for source_key, count in con.execute(
            f"select source_key, count(*) from marts.{_quote(mart)} group by all order by all"
        ).fetchall():
            per_mart.setdefault(source_key, {})[mart] = count
    found = []
    for source_key, basis, may_publish, rule, steward, provider, title, kind, reaches in con.execute(query).fetchall():
        found.append(
            {
                "source_key": source_key,
                "steward": steward or provider,
                "title": title,
                "kind": kind,
                "licence_basis": basis,
                "may_publish": may_publish,
                "publication_rule": rule,
                "reaches_hikers": reaches,
                "rows_by_mart": per_mart.get(source_key, {}),
            }
        )
    return found


def load_parity(parity_dir: Path | None) -> dict[str, dict]:
    if parity_dir is None:
        return {}
    results = {}
    for path in sorted(parity_dir.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(document, dict) and document.get("format") == PARITY_RESULT_FORMAT:
            results[document["family"]] = document
    return results


def unnamed_in_todays_files(parity: dict[str, dict]) -> list[dict]:
    """The families whose old records name no source: a source carried only there cannot be seen by new_sources()."""
    return [
        {"family": family, "file": result.get("new_file_name"), "records": result["old_records_naming_no_source"]}
        for family, result in sorted(parity.items())
        if result.get("old_records_naming_no_source")
    ]


def new_sources(con, tables: dict, parity: dict[str, dict], may_publish: dict[str, bool]) -> list[dict]:
    """Every closure, warning, water and shelter source the marts carry, and whether today's files carry it."""
    found = []
    for mart, label, named_as, type_column, where, needs in NEW_SOURCE_QUERIES:
        columns = tables.get(("marts", mart))
        if columns is None or not set(needs) <= columns:
            continue
        club = _quote("club") if "club" in columns else "null"
        query = f"""
            select {club}, source_key, {named_as}, cast({_quote(type_column)} as varchar), count(*)
            from marts.{_quote(mart)} where {where} group by all order by all
        """
        for club_value, source_key, named, kind, count in con.execute(query).fetchall():
            today = {
                family: result["old_sources"][named]
                for family, result in parity.items()
                if named in (result.get("old_sources") or {})
            }
            if not parity:
                verdict, detail = "not_measured", "no --parity-dir, so today's files were not read"
            elif today:
                verdict = "published_today"
                detail = "today's exporter writes " + ", ".join(f"{count} in {family}" for family, count in sorted(today.items()))
            else:
                verdict = "not_in_todays_compared_files"
                detail = f"no record in the {len(parity)} files parity compared names it"
            found.append(
                {
                    "line": label,
                    "mart": mart,
                    "club": club_value,
                    "source_key": source_key,
                    "source_named_as": named,
                    "type": kind,
                    "rows": count,
                    "may_publish": may_publish.get(source_key),
                    "today": verdict,
                    "detail": detail,
                }
            )
    order = {"not_in_todays_compared_files": 0, "not_measured": 1, "published_today": 2}
    return sorted(found, key=lambda row: (order[row["today"]], row["line"], row["mart"], str(row["source_key"])))


def _cell(value) -> str:
    text = "—" if value is None else ("yes" if value is True else "no" if value is False else str(value))
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict) -> str:
    inputs = report["inputs"]
    counts, layer_rows, sources = report["mart_counts"], report["layers"], report["new_sources"]
    new = [row for row in sources if row["today"] != "published_today"]
    held = [row for row in layer_rows if not row["may_publish"]]
    lines = [
        "# New-data review: what the marts carry that parity cannot check",
        "",
        f'Decision 31 (pipeline/ELT.md, "The go/no-go gate"). Warehouse `{inputs["warehouse"]}`; parity results '
        f"{'`' + inputs['parity_dir'] + '`' if inputs['parity_dir'] else 'not given'}.",
        "",
        f"- {sum(row['rows'] for row in counts):,} mart rows across {len({row['mart'] for row in counts})} marts.",
        f"- {len(layer_rows)} layers in `int_sources__publication`: {len(layer_rows) - len(held)} may publish, {len(held)} may not.",
        f"- {len(sources)} closure, warning, water and shelter sources; **{len(new)} not seen in today's compared files**.",
        "",
        "Counts, source keys and registry fields only: no person field and no location is in this report.",
        "",
        "## Closure, warning, water and shelter sources, line by line",
        "",
        'Not seen first. "Today" is what today\'s exporters wrote on the same input, as parity.py counted it by the '
        "source each record names (`source`, `source_key`, `closure_source`). Only the files parity compared were "
        'read, so a file with no parity line (gate_report.md\'s "not yet ported" keys) is not among them, and a '
        "source carried only in a file whose records name no source cannot be seen here: "
        + (", ".join(f"{row['file']} ({row['records']:,} records)" for row in report["todays_files_naming_no_source"]) or "none")
        + ".",
        "",
        "| Line | Mart | Club | Source key | Named in the file as | Type | Rows | May publish | Today |",
        "|---|---|---|---|---|---|---|---|---|",
        *(
            f"| {row['line']} | {row['mart']} | {_cell(row['club'])} | `{row['source_key']}` | `{row['source_named_as']}` | "
            f"{_cell(row['type'])} | {row['rows']:,} | {_cell(row['may_publish'])} | {_cell(row['detail'])} |"
            for row in sources
        ),
        "",
        "## Licence basis and may_publish, per layer",
        "",
        "| Source key | Steward | Kind | Licence basis | May publish | Rule | Rows by mart |",
        "|---|---|---|---|---|---|---|",
        *(
            f"| `{row['source_key']}` | {_cell(row['steward'])} | {_cell(row['kind'])} | {_cell(row['licence_basis'])} | "
            f"{_cell(row['may_publish'])} | {_cell(row['publication_rule'])} | "
            f"{_cell(', '.join(f'{mart} {count:,}' for mart, count in row['rows_by_mart'].items()) or None)} |"
            for row in sorted(layer_rows, key=lambda row: (bool(row["may_publish"]), row["source_key"]))
        ),
        "",
        "## Rows per org × type × mart",
        "",
        "| Mart | Club | Type | Rows |",
        "|---|---|---|---|",
        *(
            f"| {row['mart']} | {_cell(row['club'])} | {_cell(row['type'])}"
            f"{'' if row['type_column'] else ' (no type column)'} | {row['rows']:,} |"
            for row in counts
        ),
        "",
        "## Map shots, per region",
        "",
        MAP_SHOTS,
        "",
    ]
    return "\n".join(lines)


def build_report(warehouse: Path, parity_dir: Path | None) -> dict:
    import duckdb

    if not warehouse.exists():
        raise FileNotFoundError(f"{warehouse} is missing; build it first (build_marts.py)")
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        # Every query is a grouped count over named columns, so this needs
        # little memory and leaves a shared runner room. Reasoned: nobody
        # has run it on a real warehouse yet, which would measure it.
        con.execute("set memory_limit = '1500MB'")
        con.execute("set threads = 2")
        tables = _tables(con)
        layer_rows = layers(con, tables)
        parity = load_parity(parity_dir)
        may_publish = {row["source_key"]: row["may_publish"] for row in layer_rows}
        report = {
            "format": REPORT_FORMAT,
            "inputs": {
                "warehouse": str(warehouse),
                "parity_dir": None if parity_dir is None else str(parity_dir),
                "parity_families": sorted(parity),
            },
            "mart_counts": mart_counts(con, tables),
            "layers": layer_rows,
            "new_sources": new_sources(con, tables, parity, may_publish),
            "todays_files_naming_no_source": unnamed_in_todays_files(parity),
            "map_shots": MAP_SHOTS,
        }
    finally:
        con.close()
    refuse_what_it_must_not_hold(report, person_fields())
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--warehouse", type=Path, default=Path("data/warehouse.duckdb"), help="the built warehouse")
    parser.add_argument("--out", type=Path, required=True, help="where new_data_report.md and new_data_report.json are written")
    parser.add_argument(
        "--parity-dir", type=Path, default=None, help="parity.py --json-dir's results, to say what today's files carry"
    )
    args = parser.parse_args(argv)
    try:
        report = build_report(args.warehouse, args.parity_dir)
    except (FileNotFoundError, ValueError) as problem:
        print(f"new_data_report: {problem}", file=sys.stderr)
        return 2
    markdown = render_markdown(report)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "new_data_report.md").write_text(markdown, encoding="utf-8")
    (args.out / "new_data_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    new = sum(row["today"] != "published_today" for row in report["new_sources"])
    print(
        f"new_data_report: {len(report['layers'])} layers, {len(report['new_sources'])} closure/warning/water/shelter "
        f"sources ({new} not in today's compared files); wrote {args.out / 'new_data_report.md'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
