"""Write the dbt base and staging models of every club notice source the extract declares (decision 53, phase C).

    python generate_notice_models.py           # write every file below
    python generate_notice_models.py --check   # exit 1, naming each file, where what is on disk differs

pipeline/ELT.md, "Every club's closures and alerts (decision 53)", phase C:
"One base and staging model per source, generated from its reader's shape,
keyed per decision 40." This is that generator, and its output is committed:
tests/test_generated_notice_models.py fails when a file on disk is not what it
writes, so a source registered in extract/ without re-running it fails the
pipeline suite rather than staying unstaged.

WHAT IT READS, and nothing else: the extract's own declarations
(extract/_contract.py's discover(), every `closures` and `warnings` resource of
every club folder and _shared/ folder), each resource's sources.json row
(its `id_field`, title and notes), and two reviewed seeds:
dbt/seeds/notice_source_fields.csv, which names an ArcGIS layer's title,
status, date and link fields (the one reader whose fields differ per layer),
and nothing else. Every other reader's shape is its own, fixed in READERS
below from the module that lands it. So a new FeedNotices, PageNotice or
WordpressPosts source is staged by re-running this, with nothing to edit.

WHAT IT WRITES, per notice source (club folder C, raw table raw_C__K):
- models/staging/C/notices/base/base_C__K.sql: every column, keyed and
  deduped (decision 40), the geometry cast; nothing filtered or joined. The
  raw table is read through notice_raw_table(), which reads an empty table
  of the same key columns where the raw table does not exist, because a
  conditions leg withdraws an unreadable table (extract/_warehouse.py) and
  takes on ten new tables a run (extract/_run.py's NEW_TABLES_PER_LEG_RUN):
  one missing table must not stop every club's closures from building.
- models/staging/C/notices/stg_C__K.sql: the notice shape every club notice
  shares (int_closures__club_notices_unioned), read by name out of the row's
  JSON so that a field the layer renames reads as null rather than failing
  the build. Only facts cross: the id, title, category, status, the dates,
  the link, a place name and the source's own geometry. Prose stays in base
  (decision 55), and int_warnings__notice_wording_unioned collects it so a
  test can tell if any of it reaches a mart.
- the three YAML files beside them, and per club its sources block.
And once: dbt/seeds/notice_readers.csv (every closures and warnings resource,
hand-staged ones included: its key, club, type, reader, listing and raw
table), and the two unions, int_closures__club_notices_unioned and
int_warnings__notice_wording_unioned.

WHAT IT SKIPS: a raw table a hand-written sources block already declares
(ATC's, NYNJTC's, NYS Parks' closures, OurHike's own, NWS's): those have
their own models, which the closures family reads branch by branch.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# The four shapes the published docs site may not carry (WKT with a number,
# GeoJSON coordinates, a lat/lon value, a decimal pair): a registry note
# quoted into a model's comment or description is published there.
from check_docs_site import SHAPES as DOCS_SITE_SHAPES

PIPELINE_DIR = Path(__file__).resolve().parent
DBT_DIR = PIPELINE_DIR / "dbt"
STAGING_DIR = DBT_DIR / "models" / "staging"
CLOSURES_DIR = DBT_DIR / "models" / "intermediate" / "closures"
WARNINGS_DIR = DBT_DIR / "models" / "intermediate" / "warnings"
SEEDS_DIR = DBT_DIR / "seeds"
FIELDS_SEED = SEEDS_DIR / "notice_source_fields.csv"
READERS_SEED = SEEDS_DIR / "notice_readers.csv"
#: Where each club folder's organization type is recorded (stewards_kinds()).
TRAIL_ORGS = PIPELINE_DIR / "reference" / "trail_orgs.json"
#: trail_orgs.json's `type`s that are a club: an organization of hikers that
#: maintains its trails. Every other type there (federal, state_agency,
#: state_clearinghouse) is an agency, and so is a notice folder trail_orgs.json
#: has no row for: the folder contract makes a club folder of every
#: trail_orgs.json row but its umbrellas, route-only trails and aggregators
#: (the dlt skill, "The folder contract"), so a folder outside it is one of
#: extract/_shared/'s land managers, ma_dcr and nifc among them (measured
#: 2026-10-04: 19 such notice folders, every one under extract/_shared/).
CLUB_TYPES = frozenset({"at_club", "land_trust", "nht_org", "nst_org", "regional_nonprofit"})
UNION_MODEL = CLOSURES_DIR / "int_closures__club_notices_unioned.sql"
UNION_YML = CLOSURES_DIR / "_closures__club_notices_unioned.yml"
WORDING_MODEL = WARNINGS_DIR / "int_warnings__notice_wording_unioned.sql"
WORDING_YML = WARNINGS_DIR / "_warnings__notice_wording_unioned.yml"
#: The region box each generated notice source's closed and alert areas are held to (render_regions()).
REGIONS_MACRO = DBT_DIR / "macros" / "generated_notice_regions.sql"
#: The widest box macros/lands_outside_its_region.sql draws that still catches a swapped United States point, as
#: make_dbt_staging.py's DEFAULT_REGION is for the generated layers. Before it a notice source fell to the macro's
#: `eastern`: soak run 525 (publish-conditions.yml 37216623795), the first to read real club notices, failed
#: closures_areas_land_in_the_region_their_source_publishes_in on 148 closures and the warnings' test on 22, from
#: clubs west of lon -90 among the 163 that pass the gate (Reasoned: which sources, the log did not say).
#: @unvalidated as a fit: a source's narrowest box is what its areas' vertices on a live build show.
NOTICE_REGION = "us_and_territories"
#: Branches per part of each union. Measured 2026-10-04 on 3df39f10's fixtures: the wording union's 264
#: branches as one query stalled on DuckDB 1.5.4, the build dbt 2.0.6's ADBC driver bundles (a dbt build that
#: finished neither union in 20 minutes; in Python, 258 branches stalled on 1 run in 3 and 264 on 1 in 1,
#: while 250 ran 3 of 3 and 230, 180 and 100 ran 4 of 4, each in about a second). DuckDB 1.5.5 ran all 264, 8
#: runs of 8, and so did 1.5.4 on one thread. So each union is built in parts of at most this many branches,
#: each its own table, and the named union reads the parts. 64 is a quarter of where the stalls began: one
#: 64-source wording part ran 10 of 10 on 1.5.4, and dbt built the ten parts and both unions 3 times of 3, in
#: about 35 s each. @unvalidated as a bound, not a cause found: what settles it is the driver's DuckDB moving
#: past 1.5.4.
UNION_PART_SIZE = 64
NOTICE_TYPES = ("closures", "warnings")
#: Written on the first line of every file this writes, so the next run knows its own output from a person's.
MARKER = "GENERATED by pipeline/generate_notice_models.py"
#: The roles a notice's facts fill, in the staged column order. `link` and `locality` are text as the source states them.
ROLES = ("title", "category", "status", "starts", "ends", "rescinded", "edited", "link", "locality")
DATE_ROLES = frozenset({"starts", "ends", "rescinded", "edited"})
#: ArcGIS's server row ids. Decision 40: never one of these alone, so the geometry joins them in the key.
SERVER_ROW_IDS = frozenset({"objectid", "objectid_1", "fid", "oid"})


@dataclass(frozen=True)
class Reader:
    """How one extract reader's rows are staged: its key columns, its roles and whether it lands a geometry.

    `roles` maps a role to the raw column (dlt's lowercased name) or `column.$path` for a value inside a
    JSON column; an ArcGIS layer's come from the fields seed instead. `listing` is `window` for a reader
    whose answer is the newest items rather than the whole list (extract/_notices.py's FeedNotices).
    """

    name: str
    spatial: bool
    listing: str = "full"
    key: tuple[str, ...] = ()
    roles: dict = field(default_factory=dict)
    lists: frozenset = frozenset()
    why: str = ""


#: Every reader a closures or warnings resource may use, by class name. A resource of a class not here stops
#: the generator, so a new reader is staged on purpose. Each shape is the reader's own column_hints().
READERS = {
    "ArcgisLayer": Reader(
        "arcgis_layer",
        spatial=True,
        why="extract/_kinds.py's ArcgisLayer: every field the layer lists but its person fields, and a GeoJSON geometry",
    ),
    "FeedNotices": Reader(
        "feed_notices",
        spatial=False,
        listing="window",
        key=("item_id",),
        roles={"title": "title", "category": "categories", "starts": "published", "edited": "updated", "link": "link"},
        lists=frozenset({"categories"}),
        why="extract/_notices.py's FEED_COLUMNS: an RSS or Atom item's id, title, link, its own dates and categories",
    ),
    "PageNotice": Reader(
        "page_notice",
        spatial=False,
        key=("url",),
        roles={"title": "title", "edited": "date", "link": "url"},
        why="extract/_notices.py's PAGE_COLUMNS: one notice a page, its title, its own stated date and the link",
    ),
    "WordpressPosts": Reader(
        "wordpress_posts",
        spatial=False,
        key=("id",),
        roles={"title": "title.$.rendered", "edited": "modified_gmt", "link": "link"},
        why="extract/_kinds.py's WordpressPosts: a post as WordPress serves it, `content` and `excerpt` left in base",
    ),
    "NpsAlerts": Reader(
        "nps_alerts",
        spatial=False,
        key=("id",),
        roles={"title": "title", "category": "category", "edited": "lastindexeddate", "link": "url", "locality": "parkcode"},
        why="extract/_json_apis.py's NPS_ALERT_TEXT; `description` is NPS's wording and stays in base",
    ),
    "NpsRoadEvents": Reader(
        "nps_road_events",
        spatial=True,
        key=("id",),
        roles={
            "title": "core_details.$.name",
            "category": "core_details.$.event_type",
            "status": "vehicle_impact",
            "starts": "start_date",
            "ends": "end_date",
            "edited": "core_details.$.update_date",
            "locality": "data_source_organization",
        },
        why="extract/_json_apis.py's NpsRoadEvents: a WZDx 4.1 event with its line",
    ),
    "DcnrParkAdvisories": Reader(
        "dcnr_park_advisories",
        spatial=False,
        key=("advisory_key",),
        roles={"status": "isalert", "locality": "park_id"},
        why="extract/_json_apis.py's DcnrParkAdvisories: an advisory is {IsAlert, Message} and nothing else, so it has no title",
    ),
    "UsgsElevatedVolcanoes": Reader(
        "usgs_elevated_volcanoes",
        spatial=False,
        key=("vnum",),
        roles={
            "title": "volcano_name",
            "category": "alert_level",
            "status": "color_code",
            "edited": "sent_utc",
            "link": "notice_url",
            "locality": "obs_abbr",
        },
        why="extract/_json_apis.py's USGS_VOLCANO_TEXT; `notice_data` is USGS's wording and stays in base",
    ),
    "MediawikiAnnouncements": Reader(
        "mediawiki_announcements",
        spatial=False,
        key=("pageid",),
        roles={"title": "title", "edited": "touched", "link": "fullurl"},
        why="extract/_json_apis.py's MEDIAWIKI_PAGE_TEXT; `content` is the club's wikitext and stays in base",
    ),
    "SheetCsvSegments": Reader(
        "sheet_csv_segments",
        spatial=False,
        key=("table_title", "sect", "begin_mile", "end_mile"),
        roles={"title": "sect", "category": "table_title", "edited": "report_date", "locality": "ranger_district"},
        why="extract/_json_apis.py's SHEET_COLUMNS; `description` and `comments` are the club's wording and stay in base",
    ),
    "MyMapsPlacemarks": Reader(
        "mymaps_placemarks",
        spatial=True,
        key=("folder", "name"),
        roles={"title": "name", "category": "folder"},
        why="extract/_json_apis.py's MyMapsPlacemarks; `description` is the map's own text and stays in base",
    ),
}
#: Readers whose tables are not notices on their own: a WordPress site's place terms are a lookup the posts
#: resolve against (extract/_kinds.py's WordpressTerms), staged with their posts by hand where one is used.
NOT_NOTICES = frozenset({"WordpressTerms"})


def _normalize(name: str) -> str:
    """dlt's name for a column: sql_ci_v1, the convention .dlt/config.toml and extract/_run.py set."""
    from dlt.common.normalizers.naming.sql_ci_v1 import NamingConvention

    return NamingConvention().normalize_identifier(name)


def _column(spec: str) -> tuple[str, str | None]:
    """(the raw column, the JSON path inside it or None) for a role's field, `column` or `column.$path`."""
    column, _, path = spec.partition(".$")
    return _normalize(column), ("$" + path) if path else None


def _sql_string(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _registry() -> dict[str, dict]:
    return {row["key"]: row for row in json.loads((PIPELINE_DIR / "sources.json").read_text())["sources"]}


def _fields_seed() -> dict[str, dict]:
    with FIELDS_SEED.open(newline="") as handle:
        return {row["source_key"]: row for row in csv.DictReader(handle)}


def hand_staged_tables(root: Path = STAGING_DIR) -> set[str]:
    """Every raw table a sources block this generator did not write declares."""
    tables = set()
    for path in root.rglob("_*__sources.yml"):
        text = path.read_text()
        if MARKER in text.splitlines()[0]:
            continue
        for source in (yaml.safe_load(text) or {}).get("sources") or []:
            tables.update(table["name"] for table in source.get("tables") or [])
    return tables


@dataclass(frozen=True)
class NoticeSource:
    """One closures or warnings resource, as this generator stages it."""

    club: str
    type: str
    key: str
    table: str
    reader_class: str
    cadence: str
    hand_staged: bool
    entry: dict | None

    @property
    def reader(self) -> Reader:
        return READERS[self.reader_class]

    @property
    def stem(self) -> str:
        """The raw table's name without `raw_<club>__`: the models' second half."""
        return self.table.removeprefix(f"raw_{self.club}__")

    @property
    def base_model(self) -> str:
        return f"base_{self.club}__{self.stem}"

    @property
    def stg_model(self) -> str:
        return f"stg_{self.club}__{self.stem}"

    @property
    def folder(self) -> Path:
        return STAGING_DIR / self.club / "notices"


def notice_sources() -> list[NoticeSource]:
    """Every closures and warnings resource the extract declares, in discover()'s order, each table once."""
    from extract._contract import all_resources, discover, discover_shared

    registry = _registry()
    hand = hand_staged_tables()
    found, seen = [], set()
    for resource in all_resources(discover() + discover_shared()):
        if resource.type not in NOTICE_TYPES or resource.table in seen:
            continue
        seen.add(resource.table)
        reader_class = type(resource).__name__
        if reader_class in NOT_NOTICES:
            continue
        is_hand = resource.table in hand
        if not is_hand and reader_class not in READERS:
            raise SystemExit(
                f"{resource.club}/{resource.type}.py's {resource.key} is a {reader_class}, which READERS has no shape for: "
                "add one, read off the reader's column_hints()"
            )
        found.append(
            NoticeSource(
                club=resource.club,
                type=resource.type,
                key=resource.key,
                table=resource.table,
                reader_class=reader_class,
                cadence=resource.cadence,
                hand_staged=is_hand,
                entry=registry.get(resource.key),
            )
        )
    return found


def _key_columns(source: NoticeSource) -> list[str]:
    """The raw columns the key is built from: the reader's own, or the sources.json row's measured `id_field`."""
    if source.reader.key:
        return list(source.reader.key)
    id_field = (source.entry or {}).get("id_field")
    if not id_field:
        raise SystemExit(f"{source.key}: an ArcGIS notice layer needs its measured `id_field` on its sources.json row")
    return [_normalize(id_field)]


def _uses_geometry_in_key(source: NoticeSource) -> bool:
    return source.reader.spatial and any(column in SERVER_ROW_IDS for column in _key_columns(source))


def _roles(source: NoticeSource, fields: dict[str, dict]) -> dict[str, str]:
    if source.reader_class != "ArcgisLayer":
        return dict(source.reader.roles)
    row = fields.get(source.key)
    if row is None:
        raise SystemExit(f"{source.key}: an ArcGIS notice layer needs a row in {FIELDS_SEED.relative_to(PIPELINE_DIR)}")
    return {role: row[role] for role in ROLES if row.get(role)}


def _measured(source: NoticeSource) -> str:
    """The sentence of the row's notes that records the key's measurement, or what says nobody recorded one."""
    notes = (source.entry or {}).get("notes") or ""
    for sentence in re.split(r"(?<=\.)\s+", notes):
        if re.search(r"\b(distinct on|unique on)\b", sentence):
            return _publishable(sentence.strip())
    return "no count is recorded on its sources.json row"


def _publishable(sentence: str) -> str:
    """The sentence, or where the docs site would read part of it as a coordinate, only its clause naming the key.

    NPS's road events note reads "Each feature: LineString (78) or ...", which
    check_docs_site.py's WKT shape matches as it would a real geometry. The
    clause carrying the count is the part a reader needs, so that is kept.
    """
    if not any(shape.search(sentence) for shape in DOCS_SITE_SHAPES.values()):
        return sentence
    for clause in _clauses(sentence):
        if re.search(r"\b(distinct on|unique on)\b", clause):
            if not any(shape.search(clause) for shape in DOCS_SITE_SHAPES.values()):
                return clause.rstrip(".") + " (sources.json's notes, in part)"
    return "its sources.json row's notes record it, in words the docs site would read as a coordinate"


def _clauses(sentence: str) -> list[str]:
    """The sentence split at each comma or semicolon outside brackets."""
    clauses, depth, start = [], 0, 0
    for i, char in enumerate(sentence):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char in ",;" and depth == 0:
            clauses.append(sentence[start:i].strip())
            start = i + 1
    clauses.append(sentence[start:].strip())
    return clauses


def _wrap(text: str, width: int = 76, prefix: str = "-- ") -> list[str]:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width - len(prefix):
            lines.append(prefix + line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    if line:
        lines.append(prefix + line)
    return lines


def _title(source: NoticeSource) -> str:
    return (source.entry or {}).get("title") or source.key


def render_base(source: NoticeSource) -> str:
    keys = _key_columns(source)
    key_items = [f'"{_sql_string(source.key)}"'] + [f"'{column}'" for column in keys]
    if _uses_geometry_in_key(source):
        key_items.append("geometry_key('geom')")
    empty_columns = (["geometry"] if source.reader.spatial else []) + keys
    lines = [f"-- {MARKER}; do not edit by hand.", "--"]
    lines += _wrap(
        f"{_title(source)} (sources.json `{source.key}`, landed by extract/{source.club}/{source.type}.py's "
        f"{source.reader_class}): every row, keyed and deduped (decision 40), with nothing filtered and nothing "
        "joined. Its words, prose included, stay here: the staging model beside it carries only facts (decision 55)."
    )
    lines.append("--")
    key_text = f"Key: {', '.join(keys)}"
    if _uses_geometry_in_key(source):
        key_text += (
            ", a server row id, so the geometry joins it (decision 40: never a server row id alone). A reload that "
            "mints the ids again reads as every notice removed and added, which moves a row's dates and never its "
            "presence. @unvalidated as the smallest set of current values: pipeline/spike_table_keys.py on the live "
            "layer settles it"
        )
    lines += _wrap(f"{key_text}. Measured: {_measured(source)}")
    lines.append("--")
    lines += _wrap(
        "Read through notice_raw_table(): a table a conditions leg has not loaded, or has withdrawn as unreadable, "
        "reads as no rows here rather than stopping every other club's closures."
    )
    source_call = f"source({_sql_string(source.club)}, {_sql_string(source.table)})"
    if len(source_call) + 9 > MAX_LINE:
        source_call = f"source(\n            {_sql_string(source.club)},\n            {_sql_string(source.table)}\n        )"
    empty = ", ".join(_sql_string(column) for column in empty_columns)
    version_call = f"source({_sql_string(source.club)}, {_sql_string(source.table)})"
    if len(version_call) + 12 > MAX_LINE:
        version_call = (
            f"source(\n                {_sql_string(source.club)},\n                {_sql_string(source.table)}\n            )"
        )
    version = ["        {{ notice_row_version(", f"            {version_call}", "        ) }} as row_version"]
    if source.reader.spatial:
        select = [
            "    select",
            "        * exclude (geometry),",
            "        st_geomfromgeojson(cast(geometry as varchar)) as geom,",
            *version,
        ]
    else:
        select = ["    select", "        *,", *version]
    lines += ["with source as ("]
    lines += select
    lines += ["    from {{ notice_raw_table(", f"        {source_call},", f"        [{empty}]", "    ) }}", "),", ""]
    lines += ["keyed as (", "    select", "        {{ dbt_utils.generate_surrogate_key(["]
    lines += [f"            {item}," for item in key_items]
    lines += ["        ]) }} as notice_key,", "        source.*", "    from source", "),", ""]
    lines += [
        "-- How many different rows share each key. More than one is what",
        "-- duplicates_are_exact fails on, which only warns for a club notice",
        "-- source: int_closures__gate holds the source instead, so one club's",
        "-- conflicting rows hold that club's notices and nothing else.",
        "renamed as (",
        "    select",
        "        keyed.*,",
        "        count(distinct keyed.row_version)",
        "            over (partition by keyed.notice_key)",
        "            as key_versions",
        "    from keyed",
        ")",
        "",
    ]
    lines += ["{{ dbt_utils.deduplicate(", "    relation='renamed', partition_by='notice_key', order_by='_dlt_id'", ") }}"]
    return "\n".join(lines) + "\n"


def _field_call(spec: str, lists: frozenset) -> str:
    """macros/notices.sql's notice_field() for a role's field, as a Jinja call without its braces."""
    column, path = _column(spec)
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", column):
        raise SystemExit(f"{spec}: dlt names a column in lowercase letters, digits and underscores, so this is not one")
    arguments = [_sql_string(column)]
    if path:
        arguments.append(_sql_string(path))
    if column in lists:
        arguments.append("as_list=true")
    return f"notice_field({', '.join(arguments)})"


def _text_expression(spec: str, lists: frozenset) -> str:
    return "{{ " + _field_call(spec, lists) + " }}"


def _instant_expression(spec: str, lists: frozenset) -> str:
    return "{{ notice_instant(" + _field_call(spec, lists) + ") }}"


#: SQLFluff's LT05 limit, which every generated line keeps to (pipeline/.sqlfluff).
MAX_LINE = 80


def _column_lines(expression: str, name: str) -> list[str]:
    """One staged column, on one line where it fits and with its Jinja call split where it does not."""
    line = f"    {expression} as {name},"
    if len(line) <= MAX_LINE:
        return [line]
    inner = expression.removeprefix("{{ ").removesuffix(" }}")
    head, _, rest = inner.partition("(")
    return [f"    {{{{ {head}(", f"        {rest[:-1]}", f"    ) }}}} as {name},"]


def render_stg(source: NoticeSource, fields: dict[str, dict]) -> str:
    roles = _roles(source, fields)
    keys = _key_columns(source)
    lines = [f"-- {MARKER}; do not edit by hand.", "--"]
    lines += _wrap(
        f"{_title(source)} (sources.json `{source.key}`) in the shape every club notice shares "
        f"(int_closures__club_notices_unioned): renames and casts only. Each field is read by its own name out of "
        f"the row as JSON, so a field the source drops or renames reads as null rather than failing every club's "
        f"build. The reader's shape: {source.reader.why}."
    )
    if source.reader_class == "ArcgisLayer":
        lines += _wrap(
            "Its fields are the layer's own, named in seeds/notice_source_fields.csv from the field list the "
            "decision 53 inventory read (2026-10-03); a role the layer has no field for is null, never filled in."
        )
    lines.append("--")
    lines += _wrap(
        "Only facts cross from base_: the source's id, title, category, status, dates, link, a place name and its "
        "own geometry (decision 55, and ORG_NOTICES.md section 7). Classifying a status, holding back an ended "
        "notice and placing it are int_closures__club_notices' work."
    )
    lines += ["with base as (", "    select *", f"    from {{{{ ref({_sql_string(source.base_model)}) }}}}", "),", ""]
    lines += [
        "attributes as (",
        "    select * exclude (geom)" if source.reader.spatial else "    select *",
        "    from base",
        "),",
        "",
    ]
    # Unqualified throughout: `to_json(attributes)` names the row, which dbt
    # lint's RF03 reads as an unqualified reference, so the columns beside it
    # are unqualified too, the one consistent style it accepts.
    lines += [
        "fields as (",
        "    select",
        "        notice_key,",
        "        key_versions,",
        "        _loaded_at,",
        "        to_json(attributes) as row_json",
        "    from attributes",
        ")",
        "",
        "select",
        "    fields.notice_key,",
        f"    {_sql_string(source.key)} as source_key,",
        f"    {_sql_string(source.club)} as club,",
        f"    {_sql_string(source.type)} as notice_type,",
        f"    {_sql_string(source.reader.name)} as reader,",
        f"    {_sql_string(source.reader.listing)} as listing,",
    ]
    id_parts = [_text_expression(column, frozenset()) for column in keys]
    if len(id_parts) == 1:
        lines.append(f"    {id_parts[0]} as source_id,")
    else:
        lines.append("    concat_ws(")
        lines.append("        '|',")
        lines += [f"        {part}{',' if i < len(id_parts) - 1 else ''}" for i, part in enumerate(id_parts)]
        lines.append("    ) as source_id,")
    for role in ROLES:
        spec = roles.get(role)
        name = {"starts": "starts_at", "ends": "ends_at", "rescinded": "rescinded_at", "edited": "source_edited_at"}.get(
            role, "source_url" if role == "link" else role
        )
        if spec is None:
            cast = "timestamptz" if role in DATE_ROLES else "varchar"
            lines.append(f"    cast(null as {cast}) as {name},")
        elif role in DATE_ROLES:
            lines += _column_lines(_instant_expression(spec, source.reader.lists), name)
        else:
            lines += _column_lines(_text_expression(spec, source.reader.lists), name)
    if source.reader.spatial:
        lines += [
            "    case",
            "        when base.geom is not null and not st_isempty(base.geom)",
            "            then cast(",
            "                st_asgeojson(st_setcrs(base.geom, 'OGC:CRS84')) as varchar",
            "            )",
            "    end as geom_geojson,",
        ]
    else:
        lines.append("    cast(null as varchar) as geom_geojson,")
    lines += ["    fields.key_versions,", "    fields._loaded_at", "from fields"]
    if source.reader.spatial:
        lines.append("inner join base on fields.notice_key = base.notice_key")
    return "\n".join(lines) + "\n"


def _duplicates_key(source: NoticeSource) -> list[str]:
    items = [_sql_string(source.key)] + _key_columns(source)
    if _uses_geometry_in_key(source):
        items.append("md5(st_astext(st_geomfromgeojson(cast(geometry as varchar))))")
    return items


def _exactness_severity(source: NoticeSource) -> str:
    """`warn`, for every club notice source, shipping or not, because the gate holds a conflicting source.

    A failing test on a raw table skips every model downstream of it, which for
    a notice source is every club's closures and warnings, and every
    conditions file with them: ATC's, NYNJTC's and NWS's in the hourly job,
    which reads club notices too (decision 61). So the base model counts the
    different rows on each key itself (`key_versions`, macros/notices.sql's
    notice_row_version(), the hash duplicates_are_exact compares), and
    int_closures__gate holds a source with any key over one: its notices are
    held, never published as one arbitrary copy, and every other source's
    publish. The test still names the keys, as a warning; its header's "the
    answer to a failure is a better key" stands, and the hold is what keeps
    that answer from costing every other club its closures
    (tests/test_generated_notice_models.py holds the two together).
    """
    del source
    return "warn"


def _dump(document: dict) -> str:
    return yaml.safe_dump(document, sort_keys=False, width=100, allow_unicode=True)


def is_pdf_notice(source: NoticeSource) -> bool:
    """A page notice read from a PDF: no freshness, because the fixture warehouse never holds its table.

    PageNotice reads a PDF through pypdf, which the pipeline and dbt jobs do not
    install, so fixture mode leaves these out (make_dbt_fixtures.py's note on the
    four PDFs) and CI's `dbt source freshness` would fail on a table that is not
    there. Each has a fct_sources_without_freshness row in
    seeds/dbt_project_evaluator_exceptions.csv, which
    tests/test_generated_notice_models.py holds to this list. The gate still
    holds an absent one (int_closures__notice_tables).
    """
    return source.reader_class == "PageNotice" and str((source.entry or {}).get("url", "")).lower().endswith(".pdf")


def render_sources_yml(club: str, sources: list[NoticeSource]) -> str:
    tables = []
    for source in sources:
        table = {
            "name": source.table,
            "description": (
                f"{_title(source)} (sources.json `{source.key}`), landed by extract/{source.club}/{source.type}.py's "
                f"{source.reader_class}. Key: {', '.join(_key_columns(source))}. {_measured(source)}"
            ),
            "config": {"meta": {"cadence": source.cadence}, **({"freshness": None} if is_pdf_notice(source) else {})},
            "data_tests": [
                {
                    "duplicates_are_exact": {
                        "arguments": {"key_columns": _duplicates_key(source)},
                        "config": {"severity": _exactness_severity(source)},
                    }
                }
            ],
        }
        tables.append(table)
    document = {
        "version": 2,
        "sources": [
            {
                "name": club,
                "description": (
                    f"The {club}/ extract folder's closures and warnings sources, landed as raw_{club}__<key> "
                    "and staged once each by a generated base model here (decision 53, phase C)."
                ),
                "schema": "raw",
                "config": {
                    "loaded_at_field": "_loaded_at",
                    "meta": {"cadence": "hourly"},
                    # @unvalidated, the threshold _nynjtc_alerts__sources.yml inherited: a change check
                    # that answers FRESH reloads nothing, so a quiet week reads as stale.
                    "freshness": {"warn_after": {"count": 7, "period": "day"}},
                },
                "tables": tables,
            }
        ],
    }
    return f"# {MARKER}; do not edit by hand.\n" + _dump(document)


def render_base_yml(club: str, sources: list[NoticeSource]) -> str:
    models = [
        {
            "name": source.base_model,
            "description": (
                f"{_title(source)} (sources.json `{source.key}`), every row of {source.table}, keyed and deduped "
                "(decision 40). The source's own words stay here and go no further."
            ),
            "columns": [
                {
                    "name": "notice_key",
                    "description": f"The key: the registry key, then {', '.join(_key_columns(source))}"
                    + (" and the geometry." if _uses_geometry_in_key(source) else "."),
                    "data_tests": ["unique", "not_null"],
                }
            ],
        }
        for source in sources
    ]
    return f"# {MARKER}; do not edit by hand.\n" + _dump({"version": 2, "models": models})


def render_models_yml(club: str, sources: list[NoticeSource]) -> str:
    models = [
        {
            "name": source.stg_model,
            "description": (
                f"{_title(source)} (sources.json `{source.key}`) in the shared club-notice shape: facts and a "
                "link, never the source's paragraphs (decision 55)."
            ),
            "columns": [
                {"name": "notice_key", "description": "The base model's key.", "data_tests": ["unique", "not_null"]},
            ],
        }
        for source in sources
    ]
    return f"# {MARKER}; do not edit by hand.\n" + _dump({"version": 2, "models": models})


def steward_kinds() -> dict[str, str]:
    """{club folder: `club` or `agency`}, for each folder trail_orgs.json has a row for (CLUB_TYPES says which)."""
    rows = json.loads(TRAIL_ORGS.read_text())["orgs"]
    return {row["slug"].replace("-", "_"): "club" if row["type"] in CLUB_TYPES else "agency" for row in rows}


def render_readers_seed(sources: list[NoticeSource]) -> str:
    """The seed's rows. `steward_kind` is decision 66's "clubs only" (the maintainer's poll, 2026-10-04): the
    phone's planned-hike panel shows a club's unplaced notice to a hike on that club's trails, and an agency's
    only where the notice is placed on or near the route (client/src/lib/plannedNotices.ts)."""
    kinds = steward_kinds()
    handle = io.StringIO()
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(["source_key", "club", "notice_type", "reader", "listing", "raw_table", "staged_by", "steward_kind"])
    for source in sorted(sources, key=lambda s: s.table):
        reader = READERS.get(source.reader_class)
        writer.writerow(
            [
                source.key,
                source.club,
                source.type,
                reader.name if reader else _snake(source.reader_class),
                reader.listing if reader else "full",
                source.table,
                "hand" if source.hand_staged else source.stg_model,
                kinds.get(source.club, "agency"),
            ]
        )
    return handle.getvalue()


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _parts(sources: list[NoticeSource]) -> list[list[NoticeSource]]:
    """The generated sources in raw table order, cut into UNION_PART_SIZE branches a part."""
    staged = sorted((s for s in sources if not s.hand_staged), key=lambda s: s.table)
    return [staged[start : start + UNION_PART_SIZE] for start in range(0, len(staged), UNION_PART_SIZE)]


def _part_name(model: Path, number: int) -> str:
    """int_<family>__<name>_part_<n>_unioned for model int_<family>__<name>_unioned."""
    return model.stem.removesuffix("_unioned") + f"_part_{number}_unioned"


def _union_of_parts(model: Path, sources: list[NoticeSource], what: str) -> str:
    lines = [f"-- {MARKER}; do not edit by hand.", "{{ config(materialized='table') }}"]
    lines += _wrap(what)
    lines += _wrap(
        f"Read from its parts, each a table of at most {UNION_PART_SIZE} sources' branches "
        "(UNION_PART_SIZE in pipeline/generate_notice_models.py says why: one query of every branch stalled "
        "on the DuckDB that dbt 2.0.6 bundles)."
    )
    for index in range(len(_parts(sources))):
        if index:
            lines += ["", "union all by name", ""]
        lines += ["select *", f"from {{{{ ref({_sql_string(_part_name(model, index + 1))}) }}}}"]
    return "\n".join(lines) + "\n"


UNION_WHAT = (
    "Every generated club notice source's staged rows, one row each, by name, nothing filtered "
    "(decision 53, phase C): the union int_closures__club_notices reads. One branch per stg_ model this "
    "generator writes, in raw table order; seeds/notice_readers.csv lists the same sources with their "
    "readers, and the hand-staged ones (ATC, NYNJTC, NYS Parks, OurHike, NWS) are int_closures__unioned's "
    "own branches."
)


def render_union(sources: list[NoticeSource]) -> str:
    return _union_of_parts(UNION_MODEL, sources, UNION_WHAT)


def render_union_part(part: list[NoticeSource], number: int, count: int) -> str:
    lines = [f"-- {MARKER}; do not edit by hand.", "{{ config(materialized='table') }}"]
    lines += _wrap(
        f"Part {number} of {count} of {UNION_MODEL.stem}: {len(part)} sources' staged rows, by name, in raw table "
        f"order, from {part[0].stg_model} to {part[-1].stg_model}."
    )
    for index, source in enumerate(part):
        if index:
            lines += ["", "union all by name", ""]
        lines += ["select *", f"from {{{{ ref({_sql_string(source.stg_model)}) }}}}"]
    return "\n".join(lines) + "\n"


def _fact_columns(source: NoticeSource, fields: dict[str, dict]) -> list[str]:
    """The raw columns whose values the staging model carries as facts: its key and its roles' fields."""
    columns = set(_key_columns(source))
    columns.update(_column(spec)[0] for spec in _roles(source, fields).values())
    return sorted(columns)


WORDING_WHAT = (
    "Every generated club notice source's own wording (decision 55): each text value of a base model's "
    "columns that its staging model does not carry as a fact, that equals none of that row's facts, and "
    "that notice_is_wording() reads as wording rather than a short value. One row each. "
    "int_warnings__wording_leaks reads it, and its test fails the build when a closures or warnings row "
    "carries any of it: a source's paragraphs stay in the private raw store."
)


def render_wording(sources: list[NoticeSource]) -> str:
    return _union_of_parts(WORDING_MODEL, sources, WORDING_WHAT)


def render_wording_part(part: list[NoticeSource], number: int, count: int, fields: dict[str, dict]) -> str:
    lines = [f"-- {MARKER}; do not edit by hand.", "{{ config(materialized='table') }}"]
    lines += _wrap(
        f"Part {number} of {count} of {WORDING_MODEL.stem}: {len(part)} sources' wording, in raw table order, "
        f"from {part[0].base_model} to {part[-1].base_model}."
    )
    lines += _wrap(
        "Each branch is one base model's rows as JSON with the names of the columns its staging model carries as "
        "facts; the reading below the union is the same for every source."
    )
    staged = part
    lines.append("with rows_as_json as (")
    for index, source in enumerate(staged):
        if index:
            lines += ["", "    union all by name", ""]
        facts = ", ".join(_sql_string(column) for column in _fact_columns(source, fields))
        fact_line = f"        [{facts}] as fact_columns"
        if len(fact_line) > MAX_LINE:
            fact_line = (
                "        [\n"
                + ",\n".join(f"            {_sql_string(c)}" for c in _fact_columns(source, fields))
                + "\n        ] as fact_columns"
            )
        ref_call = f"{{{{ ref({_sql_string(source.base_model)}) }}}}"
        # A subquery on every branch, so `base` is an alias the query needs: dbt
        # lint's AL05 reads `from <ref> as base` with only `to_json(base)` after
        # it as an alias never used. The geometry is never wording, and a fire
        # perimeter's text would be serialised for nothing.
        columns = "select * exclude (geom)" if source.reader.spatial else "select *"
        from_lines = ["    from (", f"        {columns}", f"        from {ref_call}", "    ) as base"]
        from_lines = [line + "  -- noqa: LT05" if len(line) > MAX_LINE else line for line in from_lines]
        lines += [
            "    select",
            f"        {_sql_string(source.key)} as source_key,",
            # Unqualified, as render_stg's `fields` is: dbt lint's RF03.
            "        notice_key,",
            "        to_json(base) as row_json,",
            fact_line,
            *from_lines,
        ]
    text = "notice_wording_text('judged.raw_text')"
    lines += [
        "),",
        "",
        "-- Every text value of every row, once, and whether its column is one the",
        "-- staging model carries as a fact.",
        "values_read as (",
        "    select",
        "        rows_as_json.source_key,",
        "        rows_as_json.notice_key,",
        "        entry.key as column_name,",
        "        json_extract_string(entry.value, '$') as raw_text,",
        "        list_contains(rows_as_json.fact_columns, entry.key) as is_fact",
        "    from rows_as_json",
        "    cross join json_each(rows_as_json.row_json) as entry",
        "    where",
        "        json_type(entry.value) = 'VARCHAR'",
        "        and entry.key not in (",
        "            'notice_key', '_loaded_at', '_dlt_id', '_dlt_load_id', 'geom'",
        "        )",
        "),",
        "",
        "-- A value a fact column of its own row already holds, whole or inside a",
        "-- longer fact, is a fact, never wording: a description that is its title",
        "-- again, or a facility's name its own title names. ma_dcr_park_alerts'",
        "-- FACILITY_ASSETCODE inside its PAdv_HeaderText title failed soak runs",
        "-- 525 to 527 (publish-conditions.yml 37218044501 the last) while it was",
        "-- read only as a whole value. Publishing the fact says nothing the fact",
        "-- does not, and both sides are read as words, as the leak test reads them.",
        "judged as (",
        "    select",
        "        values_read.*,",
        "        exists(",
        "            select 1",
        "            from values_read as fact",
        "            where",
        "                fact.is_fact",
        "                and fact.source_key = values_read.source_key",
        "                and fact.notice_key = values_read.notice_key",
        "                and contains(",
        "                    {{ notice_wording_text('fact.raw_text') }},",
        "                    {{ notice_wording_text('values_read.raw_text') }}",
        "                )",
        "        ) as repeats_a_fact",
        "    from values_read",
        ")",
        "",
        "select",
        "    {{ dbt_utils.generate_surrogate_key([",
        "        'judged.source_key', 'judged.notice_key', 'judged.column_name'",
        "    ]) }} as wording_key,",
        "    judged.source_key,",
        "    judged.notice_key,",
        "    judged.column_name,",
        "    {{ " + text + " }} as wording",
        "from judged",
        "where",
        "    not judged.is_fact",
        "    and not judged.repeats_a_fact",
        "    and {{ notice_is_wording(" + text + ") }}",
    ]
    return "\n".join(lines) + "\n"


#: The source whose base model the wording union's unit test gives a row: one with a prose column of its own.
WORDING_TEST_SOURCE = "nps_alerts"


def render_union_yml(sources: list[NoticeSource]) -> str:
    columns = [
        {"name": "notice_key", "description": "The staging model's key.", "data_tests": ["unique", "not_null"]},
        {"name": "source_key", "description": "The source's sources.json key.", "data_tests": ["not_null"]},
    ]
    model = {
        "name": UNION_MODEL.stem,
        "description": (
            "Every generated club notice source's staged rows, by name, nothing filtered: one branch per stg_ model "
            "pipeline/generate_notice_models.py writes, read from its parts. int_closures__club_notices reads it."
        ),
        "columns": columns,
    }
    parts = _parts(sources)
    models = [model] + [
        {
            "name": _part_name(UNION_MODEL, number),
            "description": (
                f"Part {number} of {len(parts)} of {UNION_MODEL.stem}: {len(part)} sources' staged rows "
                f"({part[0].stg_model} to {part[-1].stg_model})."
            ),
            "columns": columns,
        }
        for number, part in enumerate(parts, start=1)
    ]
    return f"# {MARKER}; do not edit by hand.\n" + _dump({"version": 2, "models": models})


def render_wording_yml(sources: list[NoticeSource], fields: dict[str, dict]) -> str:
    columns = [
        {
            "name": "wording_key",
            "description": "The source, the base row's key and the column.",
            "data_tests": ["unique", "not_null"],
        },
        {"name": "wording", "description": "The value as words: tags cut, whitespace folded."},
    ]
    model = {
        "name": WORDING_MODEL.stem,
        "description": (
            "Every generated club notice source's own wording (decision 55): each text value of a base model's "
            "columns that its staging model does not carry as a fact, one row each, read from its parts. "
            "int_warnings__wording_leaks reads it."
        ),
        "columns": columns,
    }
    parts = _parts(sources)
    models = [model] + [
        {
            "name": _part_name(WORDING_MODEL, number),
            "description": (
                f"Part {number} of {len(parts)} of {WORDING_MODEL.stem}: {len(part)} sources' wording "
                f"({part[0].base_model} to {part[-1].base_model})."
            ),
            "columns": columns,
        }
        for number, part in enumerate(parts, start=1)
    ]
    (tested,) = [number for number, part in enumerate(parts, start=1) if WORDING_TEST_SOURCE in {s.key for s in part}]
    given = []
    for source in parts[tested - 1]:
        if source.key == WORDING_TEST_SOURCE:
            # SQL rows, as every other branch here. An hourly warehouse with no served notices copy lands no raw
            # table for this source, so its base model has only notice_raw_table()'s key columns, and dict rows
            # naming title, description and category fail dbt's column check before a single test runs: the soak
            # run on ecc43d56 (publish-conditions.yml 37203308446) stopped there.
            given.append(
                {
                    "input": f"ref('{source.base_model}')",
                    "format": "sql",
                    "rows": (
                        "select 'k1' as notice_key, 'a1' as id, 'Fixture Trail closed' as title,"
                        " '<p>Fixture wording: the trail is closed beyond the second bridge for repairs.</p>'"
                        " as description, 'Park Closure' as category"
                        " union all select 'k2', 'a2', 'A fixture title that the description repeats',"
                        " 'A fixture title that the description repeats', 'Caution'"
                        " union all select 'k3', 'a3', 'Fixture', 'Too short.', 'Danger'"
                        " union all select 'k4', 'a4', 'An advisory is in effect for the Fixture Visitor Center"
                        " by the reservoir.', 'Fixture Visitor Center by the reservoir', 'Advisory'"
                    ),
                }
            )
        else:
            # SQL rather than `rows: []`: dbt 2.0.6 types an empty dict mock by fetching the model's
            # schema, which fails on a GEOMETRY column (_warnings__intermediate.yml's note on base_nws__alerts).
            # A spatial branch reads `* exclude (geom)`, so its mock has a `geom` to exclude.
            columns = "cast(null as varchar) as notice_key"
            if source.reader.spatial:
                columns += ", cast(null as varchar) as geom"
            given.append(
                {
                    "input": f"ref('{source.base_model}')",
                    "format": "sql",
                    "rows": f"select {columns} where false",
                }
            )
    if not any(" union all " in g["rows"] for g in given):
        raise SystemExit(f"{WORDING_TEST_SOURCE} is not a generated notice source, so the wording unit test has no row")
    unit = {
        "name": "int_warnings__notice_wording_unioned_collects_a_sources_paragraph_and_never_its_facts",
        "description": (
            "Generated with the model. A notice's description is its source's wording, read as words; its title, "
            "id and category are facts and are not; a description that repeats the title is a fact too, and so "
            "is one the title holds inside a longer sentence (a facility's name its title names); one shorter "
            "than notice_is_wording()'s threshold is not wording. Every other source's base model in the part "
            "is given no rows."
        ),
        "model": _part_name(WORDING_MODEL, tested),
        "given": given,
        "expect": {
            "rows": [
                {
                    "source_key": WORDING_TEST_SOURCE,
                    "column_name": "description",
                    "wording": "Fixture wording: the trail is closed beyond the second bridge for repairs.",
                }
            ]
        },
    }
    return f"# {MARKER}; do not edit by hand.\n" + _dump({"version": 2, "models": models, "unit_tests": [unit]})


def hand_set_regions() -> set[str]:
    """The source keys macros/lands_outside_its_region.sql's own `regions` map lists: a box somebody set by hand."""
    text = (DBT_DIR / "macros" / "lands_outside_its_region.sql").read_text()
    block = re.search(r"\{%-?\s*set regions = \{(.*?)\}\s*-?%\}", text, re.S)
    return set(re.findall(r"'([a-z0-9_]+)':", block.group(1))) if block else set()


def render_regions(sources: list[NoticeSource]) -> str:
    """macros/generated_notice_regions.sql: NOTICE_REGION for every generated notice source no hand map lists."""
    by_hand = hand_set_regions()
    keys = sorted({source.key for source in sources if not source.hand_staged and source.key not in by_hand})
    cases = "\n".join(f"    when {{{{ column }}}} = '{key}' then '{NOTICE_REGION}'" for key in keys)
    return (
        "{#- GENERATED by pipeline/generate_notice_models.py; do not edit by hand. -#}\n"
        "{#-\n"
        "    The region box each club notice source pipeline/generate_notice_models.py\n"
        "    stages holds its closed and alert areas to, as CASE branches on its key\n"
        f"    for macros/lands_outside_its_region.sql: {NOTICE_REGION}, the widest box\n"
        "    that still catches a swapped United States point (the generator's\n"
        "    NOTICE_REGION says why and what would narrow it). SQL rather than a\n"
        "    returned dict, so SQLFluff's jinja templater renders it as dbt does.\n"
        "-#}\n"
        "{% macro generated_notice_region_cases(column) -%}\n" + cases + "\n{%- endmacro %}\n"
    )


def render_all() -> dict[Path, str]:
    """{path: text} for every file this generator owns."""
    sources = notice_sources()
    fields = _fields_seed()
    files: dict[Path, str] = {}
    by_club: dict[str, list[NoticeSource]] = {}
    for source in sources:
        if source.hand_staged:
            continue
        by_club.setdefault(source.club, []).append(source)
        files[source.folder / "base" / f"{source.base_model}.sql"] = render_base(source)
        files[source.folder / f"{source.stg_model}.sql"] = render_stg(source, fields)
    for club, club_sources in by_club.items():
        folder = STAGING_DIR / club / "notices"
        files[folder / f"_{club}_notices__sources.yml"] = render_sources_yml(club, club_sources)
        files[folder / "base" / f"_{club}_notices__base.yml"] = render_base_yml(club, club_sources)
        files[folder / f"_{club}_notices__models.yml"] = render_models_yml(club, club_sources)
    files[READERS_SEED] = render_readers_seed(sources)
    files[UNION_MODEL] = render_union(sources)
    files[UNION_YML] = render_union_yml(sources)
    files[WORDING_MODEL] = render_wording(sources)
    files[WORDING_YML] = render_wording_yml(sources, fields)
    files[REGIONS_MACRO] = render_regions(sources)
    parts = _parts(sources)
    for number, part in enumerate(parts, start=1):
        files[CLOSURES_DIR / f"{_part_name(UNION_MODEL, number)}.sql"] = render_union_part(part, number, len(parts))
        files[WARNINGS_DIR / f"{_part_name(WORDING_MODEL, number)}.sql"] = render_wording_part(part, number, len(parts), fields)
    return files


def owned_on_disk() -> set[Path]:
    """Every file on disk this generator wrote: under a staging folder's notices/, and its two models and seed."""
    found = {path for path in STAGING_DIR.glob("*/notices/**/*") if path.is_file()}
    found |= set(CLOSURES_DIR.glob(f"{UNION_MODEL.stem.removesuffix('_unioned')}_part_*_unioned.sql"))
    found |= set(WARNINGS_DIR.glob(f"{WORDING_MODEL.stem.removesuffix('_unioned')}_part_*_unioned.sql"))
    owned = (READERS_SEED, UNION_MODEL, UNION_YML, WORDING_MODEL, WORDING_YML, REGIONS_MACRO)
    return found | {path for path in owned if path.exists()}


def differences(files: dict[Path, str]) -> list[str]:
    problems = []
    for path, text in sorted(files.items()):
        if not path.exists():
            problems.append(f"missing: {path.relative_to(PIPELINE_DIR)}")
        elif path.read_text() != text:
            problems.append(f"differs: {path.relative_to(PIPELINE_DIR)}")
    for path in sorted(owned_on_disk() - set(files)):
        problems.append(f"no longer written: {path.relative_to(PIPELINE_DIR)}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 where a file on disk is not what this writes")
    args = parser.parse_args(argv)
    files = render_all()
    if args.check:
        problems = differences(files)
        for problem in problems:
            print(problem)
        return 1 if problems else 0
    for path in owned_on_disk() - set(files):
        path.unlink()
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text() != text:
            path.write_text(text)
    print(f"{len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
