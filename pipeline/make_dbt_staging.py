"""Write the dbt staging layer for the clubs' registered layers from the registry, and check it.

pipeline/ELT.md, "Loading everything the clubs publish (decision 54)": "dbt models are generated, not
hand-written, wherever a layer has a measured key: a `base_<folder>__<key>` per raw table from one template,
keyed and deduped on the key the live read found, and each mart's union reading the registry for its
branches." This is that template. Its output is committed, and tests/test_dbt_generated_staging.py fails when a
committed file differs from what this would write, so a registry edit and its models land together.

    python make_dbt_staging.py           write every generated file, and delete a generated file it no longer writes
    python make_dbt_staging.py --check   write nothing; exit 1 naming each file that would change

WHICH LAYERS (registry-driven, by kind, type and measured key). Every resource that a club folder's file for
one of TYPES extracts as an ArcGIS layer (extract/_kinds.py's ArcgisLayer), a GIS file (extract/_gis_files.py's
GisFile), a geographic API (extract/_ogc.py's OgcFeatures and JsonFeatures) or a club page's or PDF's points
(extract/_pages_points.py's PagePoints and extract/_pdf_points.py's PdfPoints, decision 54's waves 4 and 5,
section S), a sources.json row of a kind in KINDS, unless a hand-written model already reads its raw table: those keep their own (the registry tables
staged before decision 54). So a layer registered later is staged by running this again, and by nothing else.
A file that SHARES a sibling's resource (one upstream feeding two types, such as a My Map of trail lines and
trailheads) gets a staging model of its own over the sibling's base model, and no second base or source: one
raw table, staged once (decision 34). An elevation file shares only a row that names its `elevation_source`.
Every base model reads its raw table through raw_or_empty() (dbt/macros/raw_or_empty.sql), so a layer that has
never landed (one the monthly extract refused on its first run, or a keyed API, `api_key_env`, whose key the job
lacks) reads as no rows with the columns its models name, and stops nothing else (Table.raw_columns()).

WHAT EACH sources.json ROW GIVES IT:
- THE KEY (decision 40): `key_fields`, else `id_fields`, else `id_field`, where `geometry` in a list stands for
  the shape (macros/geometry_key.sql) and an empty `key_fields` is a one-row layer, keyed by the registry key
  and its shape (base_pcta__centerline's precedent: a key needs a column beside the registry key). A row with
  none of these, or whose key holds a server's row id (OBJECTID, FID: a reload mints them again), STOPS the
  run and is named, so no table is staged without a measured key.
- `date_fields`: the layer's esriFieldTypeDate fields, which land as epoch milliseconds (extract/_kinds.py's
  ESRI_TYPES, "the base model converts them") and are cast to timestamptz here, in UTC as ArcGIS stores them.
  A row without it has its dates, if it has any, left as the integers dlt landed.
- per type, the fields a staging model renames to the union's columns (SHAPES): `name_field` or
  `name_constant` and `category_field` for places, `elevation_source` for elevation, `name_field` or
  `name_constant` for trail lines, and `name_field`, `type_field` and the id a point publishes under
  (`id_field`, unless it is a server row id) for points of interest. A rule a layer needs beyond these (a
  historic alignment, a road a trail layer carries, a planned trailhead, a water type that is not water) is a
  row of the dbt/seeds/layer_rules.csv seed, which the type's intermediate reads, and a point's POI type is a
  row of dbt/seeds/club_poi_types.csv.

Column names are the registry's field names as dlt names them on landing (the `sql_ci_v1` convention
.dlt/config.toml sets, path by path), quoted where DuckDB reserves the word, so `DESC_` is `"desc"`.

WHAT IT WRITES, for each club folder <f> with such layers, under dbt/models/staging/<f>/:
- `_<f>__generated__sources.yml`: each raw table, with its duplicates_are_exact test on the model's own key.
- `base/base_<f>__<key>.sql` and `base/_<f>__generated__base.yml`: one base model per raw table.
- `stg_<f>__<type>.sql` and `_<f>__generated__models.yml`: one staging model per type, every layer of that
  type in the folder conformed to its union's columns, the layer's own columns kept whole as `properties`.
And per type, under dbt/models/intermediate/<type>/: the type's union (SHAPES' `union`: `int_<type>__unioned`,
or `int_points_of_interest__club_unioned` beside the hand-written int_points_of_interest__unioned that reads it)
and its YAML, a `union all by name` of every staging model this writes for the type. And `dbt/macros/generated_regions.sql`, the region box
each generated source's rows are held to (macros/lands_outside_its_region.sql).

Every file it writes opens with GENERATED, which is how it knows which files are its own.

SECTION C'S CONTENT TYPES (decision 54 wave 3, 2026-10-04): podcasts, suggested_hikes, challenges and photos, whose
rows are episodes, write-ups, list items and photo manifest rows from feeds, APIs, WordPress and a wiki, not ArcGIS
layers. Their shapes carry `geometry=False`: no geom, no CRS cast, no region box. The tables staged are those a club
file's content reader extracts (CONTENT_COLUMNS' readers, and NPS's lists by endpoint in NPS_COLUMNS), each keyed on
its row's measured `key_fields`; a hike type's taxonomy terms (SiteTerms) are a lookup, staged in base only and keyed
on (taxonomy, id). Each type's union is `int_<type>__club_unioned`, beside the path its mart reads today, and each
staging model leaves the source's prose (CONTENT_PROSE) out of `properties`, so a body stops at the base model.

SECTION K'S PAGES AND PDFS (decision 54 waves 4 and 5, 2026-10-04): the content types a club publishes as web
pages (extract/_pages_content.py's ContentPages) and as PDFs (extract/_pdf_content.py's ContentPdf) are staged the
same way, keyed on each row's measured `key_fields`; their rows are facts by construction, so nothing is set aside
as prose. A PDF's table lands only where pypdf is installed, which is the extract job's venv and not fixture mode's
Python, so in the fixture build its base model reads no rows through raw_or_empty().
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from dataclasses import dataclass
from functools import cache
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
DBT = PIPELINE / "dbt"
MODELS = DBT / "models"
STAGING = MODELS / "staging"
INTERMEDIATE = MODELS / "intermediate"
REGIONS_MACRO = DBT / "macros" / "generated_regions.sql"

GENERATED = "GENERATED by pipeline/make_dbt_staging.py"
SQL_MARK = f"-- {GENERATED} from sources.json\n-- and the extract's club folders; edit them or it, never this file.\n"
YAML_MARK = f"# {GENERATED} from sources.json\n# and the extract's club folders; edit them or it, never this file.\n"
JINJA_MARK = f"{{#- {GENERATED} from sources.json\n    and the extract's club folders; edit them or it, never this file. -#}}\n"

#: The registry kinds an ArcgisLayer reads, then decision 54's waves 2 and 3: a GisFile, an OgcFeatures and a
#: JsonFeatures (lib/source_registry.py's GIS_FILE, OGC_FEATURES and JSON_FEATURES), then waves 4 and 5's
#: PdfPoints and PagePoints (PDF_POINTS and PAGE_POINTS). Fixture mode cannot read a PDF, because the dbt job installs
#: no pypdf (requirements.in's note), so CI's warehouse never holds a pdf_points table: its base model reads the
#: absent table as no rows (macros/raw_or_empty.sql), and the build reads its rows only where the extract landed them.
KINDS = (
    "club_arcgis_layer",
    "external_arcgis_layer",
    "gis_file",
    "ogc_features",
    "json_features",
    "page_points",
    "pdf_points",
)

#: The server row ids a key may never hold (decision 40: a truncate-and-reload mints them again), as dlt names them.
#: `feature_index` is a feature's position in its file (extract/_gis_files.py), which a re-saved file renumbers.
ROW_IDS = frozenset({"objectid", "objectid_1", "objectid_12", "fid", "oid", "esri_oid", "ogc_fid", "feature_index"})

#: What duplicates_are_exact sets aside on a file's or an OGC collection's rows, beside macros/row_hash.sql's
#: row_hash_row_ids(): two copies of one feature differ in their position in the file (`feature_index`) and in
#: the id an exporter mints per feature (`feature_id`: Catamount's GeoJSON repeats a line under ids 52 and 53,
#: measured 2026-10-04), and in nothing else.
FILE_ROW_IDS = ["objectid", "fid", "ogc_fid", "_dlt_id", "_socrata_id", "feature_index", "feature_id"]
FILE_KINDS = frozenset({"gis_file", "ogc_features"})

#: The region every generated source's rows are held to. The widest of the three boxes
#: macros/lands_outside_its_region.sql draws, and still one that catches a swapped United States point (its
#: latitude would read -64 or less). @unvalidated as a fit: no generated layer's vertices had been read when
#: this was set, and a server's own extent is never the evidence (ELT.md, "What wave 1's live reads found":
#: USFWS's answered lat -24.99 to 90 for vertices at 13.64 to 63.20). What settles each is its row of
#: int_<type>__source_extents on a live build, which names the narrowest box its vertices fit.
DEFAULT_REGION = "us_and_territories"

#: Types whose every layer already has its box decided in macros/lands_outside_its_region.sql, so the generator
#: gives them none. The trail-line rows (2026-10-03, cdaba599): that macro's map lists each one outside the eastern
#: box and its header says a row it leaves out sits inside it, so leaving one out is a decision, eastern, which a
#: generated box would widen. Those boxes were read off each layer's returnExtentOnly but one (usfws_trail_segments,
#: from its vertices), so int_trail_lines__source_extents is what checks them on a live build.
#: The point-of-interest rows the same way (2026-10-03, 643eecdf and a1c39d8c): that macro lists the 41 whose
#: points reach outside the eastern box, each boxed by every point of the layer read with outSR 4326, and its
#: header says a point row it leaves out has all its points inside the eastern box.
REGIONS_DECIDED_BY_HAND = frozenset({"trail_lines", "points_of_interest"})

LINE = 76  # SQL comment width: SQLFluff's LT05 holds every line to 80


@dataclass(frozen=True)
class Shape:
    """What one type's staging models conform to, and the union that reads them."""

    key_column: str  # <what one row is>_key (decision 40)
    row: str  # what one row is, in words
    union: str
    columns: tuple[tuple[str, str], ...]  # (column, description) beside the key, source_key, club, geom, properties, _loaded_at
    # False for a content type (section C, decision 54 wave 3): its rows are episodes, write-ups, list items and
    # photo manifest rows, with no geometry column, so no geom, no region box and no CRS cast.
    geometry: bool = True


SHAPES = {
    "places": Shape(
        key_column="place_key",
        row="one feature of a places layer: a park, a public land unit, a town, a section of trail",
        union="int_places__unioned",
        columns=(
            (
                "name",
                "The layer's own name for the feature, from the registry's `name_field`, or its `name_constant` for a layer that names its one feature only in the registry; null where it has neither.",
            ),
            ("category", "The layer's own category, from the registry's `category_field`; null where the registry names none."),
        ),
    ),
    "elevation": Shape(
        key_column="elevation_feature_key",
        row="one feature of an elevation layer: a point with a height, a line whose vertices carry one, or a band",
        union="int_elevation__unioned",
        columns=(
            (
                "published_elevation",
                "The elevation field the registry's `elevation_source` names (`field <name>`), as text, exactly as the layer publishes it; null for a layer whose elevation is its geometry's Z. Its unit is the registry's `elevation_unit`, which int_elevation__club_samples reads row by row.",
            ),
        ),
    ),
    "points_of_interest": Shape(
        key_column="poi_key",
        row="one point of a points-of-interest layer: a shelter, a campsite, a water source, a trailhead, a parking area",
        union="int_points_of_interest__club_unioned",
        columns=(
            (
                "name",
                "The layer's own name for the point, from the registry's `name_field`, or its `name_constant`; null where it has neither.",
            ),
            (
                "category",
                "The layer's own type for the point, from the registry's `type_field`, as text exactly as the layer publishes it (a coded value is its code, not its label); null where the registry names none. No value here is a POI type by itself: the club_poi_types seed maps a layer's own field values to POI types, and int_points_of_interest__club_points applies it.",
            ),
            (
                "source_id",
                "The id the point publishes under: the registry `id_field`'s value, as text, where that field is the layer's own id, and the base model's key where it is a server row id (decision 40: a reload mints OBJECTID and FID again).",
            ),
        ),
    ),
    "trail_lines": Shape(
        key_column="trail_segment_key",
        row="one line of a trail-line layer: a trail, a section, a route or an alignment, as the layer draws it",
        union="int_trail_lines__unioned",
        columns=(
            (
                "name",
                "The layer's own name for the line, from the registry's `name_field`, or its `name_constant` for a layer that names its lines only in the registry; null where it has neither.",
            ),
        ),
    ),
    # Section C's content types (decision 54 wave 3, 2026-10-04). Each union is `__club_unioned`, as
    # points_of_interest's is, because the type's mart reads another path today (the podcasts mart reads
    # reference/podcast_episodes.json's editorial picks, suggested_hikes the Hike Finder and the highlights,
    # challenges the reviewed challenge files through int_challenges__unioned) and these rows are the clubs' own
    # datasets beside it. photos has no mart: its union is the photo manifest a later step reads.
    "podcasts": Shape(
        key_column="episode_key",
        row="one episode of a club's own podcast feed, or one item of NPS's audio list",
        union="int_podcasts__club_unioned",
        columns=(
            ("title", "The episode's title as its feed or list states it."),
            (
                "published",
                "The episode's publication date as its feed states it, unparsed (RSS pubDate); null for an NPS audio item, which states none.",
            ),
            ("link", "The episode's own page, as its feed or list links it; null where it links none."),
            ("audio_url", "The audio file's URL (an RSS enclosure, or NPS's first version), linked and never fetched."),
        ),
        geometry=False,
    ),
    "suggested_hikes": Shape(
        key_column="hike_key",
        row="one hike a club or NPS publishes: a WordPress write-up, a wiki trail or hike page, an NPS thing to do or tour",
        union="int_suggested_hikes__club_unioned",
        columns=(
            ("name", "The hike's name as its source titles it (WordPress's rendered title, a wiki page's title, NPS's title)."),
            ("link", "The page a hiker reads it on, as the source links it."),
        ),
        geometry=False,
    ),
    "challenges": Shape(
        key_column="challenge_item_key",
        row="one item of a challenge list a club or NPS publishes: an NPS passport stamp location, or a club wiki's challenge page",
        union="int_challenges__club_unioned",
        columns=(
            ("name", "The item's name as its source states it (NPS's label, a wiki page's title)."),
            ("link", "The page it is published on; null where the source links none (NPS's stamp locations)."),
        ),
        geometry=False,
    ),
    "photos": Shape(
        key_column="photo_key",
        row="one photo's manifest row: its URL, its own credit and licence and its page, never its pixels",
        union="int_photos__club_unioned",
        columns=(
            ("title", "The photo's title as its source states it."),
            ("image_url", "The image file's URL, linked and never fetched (bytes never enter DuckDB, decision 4)."),
            ("credit", "The photo's own credit line, as its source states it for that photo."),
            (
                "licence",
                "The photo's own licence or constraint, as its source states it for that photo (NPS's constraintsInfo.constraint): never a park's, an account's or a site's licence.",
            ),
            ("link", "The photo's own page."),
        ),
        geometry=False,
    ),
}

#: The content readers whose tables section C stages, by class name, and each type's conformed columns per
#: reader: a raw field (written as the registry and the live answers name it, normalized as dlt lands it), a
#: JSON path into one (`field $.path`), or None for a column the reader's rows never carry.
CONTENT_COLUMNS = {
    ("podcasts", "PodcastEpisodes"): {"title": "title", "published": "pubDate", "link": "link", "audio_url": "enclosure_url"},
    ("podcasts", "NpsContent"): {},
    ("suggested_hikes", "WordpressPosts"): {"name": "title $.rendered", "link": "link"},
    ("suggested_hikes", "WordpressChildPages"): {"name": "title $.rendered", "link": "link"},
    ("suggested_hikes", "NpsContent"): {},
    ("suggested_hikes", "MediawikiTemplatePages"): {"name": "title", "link": "fullurl"},
    ("challenges", "NpsContent"): {},
    ("challenges", "MediawikiTemplatePages"): {"name": "title", "link": "fullurl"},
    ("photos", "NpsContent"): {},
    # Section K's page reader (decision 54 wave 5, extract/_pages_content.py): every type's rows carry the type's own
    # columns by these names (its TYPE_COLUMNS), whatever site they were read from.
    ("suggested_hikes", "ContentPages"): {"name": "name", "link": "link"},
    ("challenges", "ContentPages"): {"name": "name", "link": "link"},
    ("podcasts", "ContentPages"): {"title": "title", "published": "published", "link": "link", "audio_url": "audio_url"},
    ("photos", "ContentPages"): {
        "title": "title",
        "image_url": "image_url",
        "credit": "credit",
        "licence": "licence",
        "link": "link",
    },
    # Section K's PDF reader (decision 54 wave 4, extract/_pdf_content.py): the same type columns as its page reader.
    ("suggested_hikes", "ContentPdf"): {"name": "name", "link": "link"},
    ("challenges", "ContentPdf"): {"name": "name", "link": "link"},
}
#: NPS's lists, one reader for five endpoints, conformed by (type, the endpoint's path under /api/v1/), each field
#: one extract/_content.py's NPS_CONTENT_COLUMNS hints so the column exists on every run.
NPS_COLUMNS = {
    ("podcasts", "multimedia/audio"): {
        "title": "title",
        "published": None,
        "link": "permalinkUrl",
        "audio_url": "versions $[0].url",
    },
    ("suggested_hikes", "thingstodo"): {"name": "title", "link": "url"},
    ("suggested_hikes", "tours"): {"name": "title", "link": None},
    ("challenges", "passportstamplocations"): {"name": "label", "link": None},
    ("photos", "multimedia/galleries/assets"): {
        "title": "title",
        "image_url": "fileInfo $.url",
        "credit": "credit",
        "licence": "constraintsInfo $.constraint",
        "link": "permalinkUrl",
    },
}
#: The prose each reader's rows carry, by the field names the live sources served on 2026-10-04. It lands in the
#: private raw store and stops at `base_` (decision 55; the round brief's item 3: "a WordPress post's or an
#: episode's body lands in the private raw store and stops at base_"), so a staging model's `properties` sets
#: each to null, which json_merge_patch drops. A wiki page's wikitext is its prose and its template's fields
#: at once: it stops at base_ too, so a later rule that reads a trail's distance from its template parses the
#: base model, never a published column.
CONTENT_PROSE = {
    "PodcastEpisodes": ("description", "content_encoded", "itunes_summary", "itunes_subtitle", "ns_description"),
    "NpsContent": (
        "description",
        "transcript",
        "shortDescription",
        "longDescription",
        "accessibilityInformation",
        "feeDescription",
        "reservationDescription",
        "seasonDescription",
        "petsDescription",
        "locationDescription",
        "activityDescription",
        "ageDescription",
        "timeOfDayDescription",
        "durationDescription",
        "altText",
        "images",
        "stops",
    ),
    "WordpressPosts": ("content", "excerpt", "uagb_excerpt"),
    "WordpressChildPages": ("content", "excerpt"),
    "MediawikiTemplatePages": ("content",),
    # A content page's rows are facts by construction (extract/_pages_content.py's TYPE_COLUMNS allowlist): no prose
    # lands in the raw store, so none needs stopping here.
    "ContentPages": (),
    "ContentPdf": (),
}
#: The readers whose tables are lookups beside a type's rows, staged in base only: a hike type's taxonomy terms.
CONTENT_LOOKUPS = ("SiteTerms",)
#: The key of a lookup table: each term is one id within one taxonomy.
LOOKUP_KEY_FIELDS = ("taxonomy", "id")


class KeyRefused(ValueError):
    """A registry row with no usable measured key: the run stops and names it."""


@cache
def _naming():
    from dlt.common.normalizers.naming.sql_ci_v1 import NamingConvention

    return NamingConvention()


@cache
def _reserved() -> frozenset[str]:
    import duckdb

    rows = duckdb.sql("select keyword_name from duckdb_keywords() where keyword_category in ('reserved', 'type_function')")
    return frozenset(name for (name,) in rows.fetchall())


def column(field: str) -> str:
    """A registry field name as the landed column: dlt's name for it, quoted where DuckDB reserves the word."""
    name = _naming().normalize_path(field)
    return f'"{name}"' if name in _reserved() else name


def _sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


@dataclass(frozen=True)
class Table:
    folder: str
    type: str
    key: str
    table: str
    cadence: str
    entry: dict
    # The extract reader's class name: ArcgisLayer for every geographic layer (an ArcGIS layer, a GIS file or a
    # geographic API), a content reader for section C's (CONTENT_COLUMNS), which decides how the staging model
    # conforms the table's columns.
    reader: str = "ArcgisLayer"
    # The sibling type whose base model this staging reads, for a file that SHARES that sibling's resource.
    shared_from: str | None = None

    @property
    def shape(self) -> Shape:
        return SHAPES[self.type]

    @property
    def lookup(self) -> bool:
        """A lookup beside a type's rows (a hike type's terms): staged in base only, never a union branch."""
        return self.reader in CONTENT_LOOKUPS

    @property
    def key_column(self) -> str:
        return "term_key" if self.lookup else self.shape.key_column

    @property
    def base_key_column(self) -> str:
        """The key column the base model carries: its own type's, or the sibling's for a shared resource."""
        return "term_key" if self.lookup else SHAPES[self.shared_from or self.type].key_column

    @property
    def base(self) -> str:
        return f"base_{self.folder}__{self.table.removeprefix(f'raw_{self.folder}__')}"

    @property
    def title(self) -> str:
        title = self.entry.get("title") or self.key
        return f"{title}: its taxonomy terms" if self.lookup else title

    def key_inputs(self) -> list[str]:
        """The key's inputs as generate_surrogate_key takes them: the registry key, then each measured field."""
        entry = self.entry
        if self.lookup:
            return [f"'{self.key}'", *(column(field) for field in LOOKUP_KEY_FIELDS)]
        if "key_fields" in entry:
            fields, home = list(entry["key_fields"]), "key_fields"
        elif entry.get("id_fields"):
            fields, home = list(entry["id_fields"]), "id_fields"
        elif entry.get("id_field"):
            fields, home = [entry["id_field"]], "id_field"
        else:
            raise KeyRefused(f"{self.key}: no key_fields, id_fields or id_field on its sources.json row")
        if not fields:
            fields = ["geometry"]  # a one-row layer: the registry key and its shape
        inputs = [f"'{self.key}'"]
        for field in fields:
            if field == "geometry":
                inputs.append("geometry_key('geom')")
                continue
            if not isinstance(field, str) or " " in field:
                raise KeyRefused(f"{self.key}: {home} holds {field!r}, which is not one of the layer's fields")
            name = column(field)
            if name.strip('"') in ROW_IDS:
                raise KeyRefused(f"{self.key}: {home} holds {field}, a server row id, which a reload mints again (decision 40)")
            inputs.append(name)
        return inputs

    def key_comment(self) -> str:
        entry = self.entry
        if self.lookup:
            return (
                "a term's `taxonomy` and its `id`: WordPress numbers terms within one site, and the reader lands each "
                "taxonomy's terms with its name (extract/_content.py's SiteTerms), so the pair is one term."
            )
        text = entry.get("key_comment") or entry.get("id_comment")
        if text:
            return text
        home = "key_fields" if "key_fields" in entry else "id_fields" if entry.get("id_fields") else "id_field"
        return f"the registry's `{home}`; its row records no measurement of it."

    def date_columns(self) -> list[str]:
        return [column(field) for field in self.entry.get("date_fields") or []]

    def raw_columns(self) -> list[str]:
        """Every raw column the base model and the staging models over it name, as raw_or_empty() takes them.

        A table that has never landed reads as no rows with these columns (macros/raw_or_empty.sql), so every
        column a generated model names is here: the key's fields, the dates (epoch milliseconds, so bigint), the
        geometry, and each field the registry row conforms. The row's fields are all taken whichever type reads
        them, because a file that SHARES this table conforms the same row's fields over the same base model."""
        entry = self.entry
        names: dict[str, str] = {}
        for item in self.key_inputs()[1:]:  # the registry key's literal first, then the measured fields
            if item != "geometry_key('geom')":
                names.setdefault(item.strip('"'), "varchar")
        if self.shape.geometry:
            names.setdefault("geometry", "varchar")
        conformed = [entry[name] for name in ("name_field", "type_field", "category_field", "id_field") if entry.get(name)]
        elevation = entry.get("elevation_source") or ""
        if elevation.startswith("field "):
            conformed.append(elevation.removeprefix("field ").strip())
        if not self.shape.geometry and not self.lookup:
            conformed += [field.split(" ", 1)[0] for field in content_columns(self).values() if field is not None]
        for field in conformed:
            names.setdefault(column(field).strip('"'), "varchar")
        for name in self.date_columns():
            names[name.strip('"')] = "bigint"
        return [name if type_ == "varchar" else f"{name}:{type_}" for name, type_ in names.items()]


def _raw_key_columns(inputs: list[str]) -> list[str]:
    """The same key over the raw table, as duplicates_are_exact takes it: geometry_key('geom') written out."""
    raw_geometry = "md5(st_astext(st_geomfromgeojson(cast(geometry as varchar))))"
    return [raw_geometry if item == "geometry_key('geom')" else item for item in inputs]


def _hand_written_raw_tables() -> set[str]:
    """Every raw table a model this generator did not write already reads."""
    import re

    pattern = re.compile(r"source\('[a-z0-9_]+',\s*'(raw_[a-z0-9_]+)'\)")
    found = set()
    for path in MODELS.rglob("*.sql"):
        text = path.read_text()
        if GENERATED in text.split("\n", 1)[0]:
            continue
        found.update(pattern.findall(text))
    return found


def tables() -> list[Table]:
    """Every layer this stages, sorted by folder and key; stops on the first row with no usable key."""
    sys.path.insert(0, str(PIPELINE))
    from extract._contract import discover
    from extract._gis_files import GisFile
    from extract._kinds import ArcgisLayer, registry_entry
    from extract._ogc import JsonFeatures, OgcFeatures
    from extract._pages_points import PagePoints
    from extract._pdf_points import PdfPoints

    hand_written = _hand_written_raw_tables()
    readers = {reader for _, reader in CONTENT_COLUMNS} | set(CONTENT_LOOKUPS)
    geographic = ArcgisLayer | GisFile | OgcFeatures | JsonFeatures | PagePoints | PdfPoints
    files = discover()
    by_place = {(club_file.club, club_file.type): club_file for club_file in files}
    found = []
    for club_file in files:
        if club_file.type not in SHAPES:
            continue
        owner = by_place.get((club_file.club, club_file.shares)) if club_file.shares else club_file
        if owner is None or owner.type not in SHAPES:
            continue
        for resource in owner.resources:
            if resource.table in hand_written:
                continue
            reader = type(resource).__name__
            if SHAPES[club_file.type].geometry:
                if not isinstance(resource, geographic) or resource.entry.get("kind") not in KINDS:
                    continue
                reader = "ArcgisLayer"
            elif reader not in readers or (reader not in CONTENT_LOOKUPS and (club_file.type, reader) not in CONTENT_COLUMNS):
                continue
            # A keyed API's table is withdrawn whenever its key is unset (extract/_ogc.py's JsonFeatures). It is staged
            # all the same: its base model reads an absent table as no rows (macros/raw_or_empty.sql).
            entry = registry_entry(resource.key)
            if club_file.shares and club_file.type == "elevation" and not entry.get("elevation_source"):
                continue  # a line layer an elevation file shares carries its heights only where its row says so
            shared_from = owner.type if club_file.shares else None
            found.append(
                Table(club_file.club, club_file.type, resource.key, resource.table, resource.cadence, entry, reader, shared_from)
            )
    found.sort(key=lambda table: (table.folder, table.key, table.table, table.shared_from or ""))
    refused = []
    for table in found:
        try:
            table.key_inputs()
        except KeyRefused as error:
            refused.append(str(error))
    if refused:
        raise KeyRefused("no staging without a measured key (decision 40):\n  " + "\n  ".join(refused))
    return found


def _comment(text: str, indent: str = "") -> str:
    return "\n".join(textwrap.wrap(text, LINE - len(indent), initial_indent=f"{indent}-- ", subsequent_indent=f"{indent}-- "))


def _folded(text: str, indent: int) -> str:
    """A YAML folded scalar's body, wrapped."""
    pad = " " * indent
    return "\n".join(textwrap.wrap(text, 100 - indent, initial_indent=pad, subsequent_indent=pad))


def _held_back(entry: dict) -> str:
    if entry.get("reaches_hikers") is False:
        return "Its sources.json row reads `reaches_hikers: false`, so int_sources__publication holds it back from every mart."
    return "Whether it may publish is int_sources__publication's to decide, from its sources.json row."


# --- base models ----------------------------------------------------------------------------------------------


def _key_item(item: str) -> str:
    """One generate_surrogate_key input as the base models write it: the registry key as `"'<key>'"`, the
    geometry as the geometry_key('geom') call, and a column as a quoted string (tests/test_dbt_keys.py reads
    the list back with ast.literal_eval)."""
    if item.startswith("'"):
        return json.dumps(item)
    if item == "geometry_key('geom')":
        return item
    return repr(item)


def base_sql(table: Table) -> str:
    inputs = table.key_inputs()
    dates = table.date_columns()
    head = [
        _comment(
            f"{table.title} ({table.entry.get('provider') or table.folder}, sources.json `{table.key}`): every row, "
            "keyed and deduped (decision 40), with nothing filtered and nothing joined. A base model, the one place "
            "this dataset is staged (decision 34)."
        ),
        "--",
        _comment(f"Key: {table.key_comment()}"),
    ]
    if dates:
        head += ["--", _comment(f"Dates: {', '.join(dates)}, the layer's esriFieldTypeDate fields (sources.json `date_fields`).")]
    # SQLFluff's LT05 holds every line to 80: a long exclude list or source() call breaks over lines, the
    # source() call after its first argument, where tests/test_dbt_keys.py's pattern still reads it.
    excluded = ["geometry", *dates]
    exclude = f"* exclude ({', '.join(excluded)}),"
    if len(exclude) + 8 > 80:
        exclude = "* exclude (\n" + ",\n".join(f"            {name}" for name in excluded) + "\n        ),"
    # Read through raw_or_empty() (macros/raw_or_empty.sql): a table that has never landed reads as no rows with the
    # columns these models name, rather than stopping every other club's layers.
    relation = f"source('{table.folder}', '{table.table}')"
    if len(relation) + 8 > 80:
        relation = f"source('{table.folder}',\n            '{table.table}')"
    names = ", ".join(f"'{name}'" for name in table.raw_columns())
    listed = (
        f"[{names}]"
        if len(names) + 10 <= 80
        else "[\n" + "".join(f"            '{name}',\n" for name in table.raw_columns()) + "        ]"
    )
    source = f"{{{{ raw_or_empty(\n        {relation},\n        {listed}\n    ) }}}}"
    casts = "".join(f",\n        to_timestamp({name} / 1000) as {name}" for name in dates)
    key_lines = "".join(f"\n            {_key_item(item)}," for item in inputs)
    if table.shape.geometry:
        select_source = f"""    -- dlt lands geometry as GeoJSON text and an ArcGIS date as epoch
    -- milliseconds (extract/_kinds.py's ESRI_TYPES); both are cast here, as
    -- decision 40 has staging do.
    select
        {exclude}
        st_geomfromgeojson(cast(geometry as varchar)) as geom{casts}
    from {source}"""
    else:
        select_source = f"""    -- A content table carries no geometry and is cast nowhere: each column is
    -- as dlt landed it (a WordPress date a timestamp, a feed's pubDate the
    -- string it states, which a rewrite here would restate), nested as JSON.
    select *
    from {source}"""
    return (
        SQL_MARK
        + "\n".join(head)
        + f"""
with source as (
{select_source}
),

renamed as (
    select
        {{{{ dbt_utils.generate_surrogate_key([{key_lines}
        ]) }}}} as {table.key_column},
        source.*
    from source
)

{{{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='{table.key_column}', order_by='_dlt_id'
) }}}}
"""
    )


def _yaml_list(items: list[str]) -> str:
    return "[" + ", ".join(json.dumps(item) for item in items) + "]"


def sources_yaml(folder: str, folder_tables: list[Table]) -> str:
    lines = [
        YAML_MARK + "version: 2",
        "",
        "sources:",
        f"  - name: {folder}",
        "    description: >",
        _folded(
            f"The layers sources.json registers for the extract's {folder}/ folder (pipeline/extract/{folder}/) "
            f"that pipeline/make_dbt_staging.py stages, landed as raw_{folder}__<key> and staged once each by a "
            "generated base model here. Descriptions transcribed from sources.json's titles and key notes.",
            6,
        ),
        "    schema: raw",
        "    config:",
        "      loaded_at_field: _loaded_at",
        "      meta:",
        f"        cadence: {_cadence(folder_tables)}",
        "      freshness:",
        "        # The extract's cadence, not the steward's. @unvalidated, the same",
        "        # threshold and open question as _atc__sources.yml.",
        "        warn_after: {count: 7, period: day}",
        "    tables:",
    ]
    for table in folder_tables:
        lines += [
            f"      - name: {table.table}",
            "        data_tests:",
            f"          # Rows sharing {table.base}'s key must be exact copies (decision 40).",
            "          - duplicates_are_exact:",
            "              arguments:",
            f"                key_columns: {_yaml_list(_raw_key_columns(table.key_inputs()))}",
            *([f"                row_id_columns: {_yaml_list(FILE_ROW_IDS)}"] if table.entry.get("kind") in FILE_KINDS else []),
            "        description: >",
            _folded(f"{table.title} (sources.json `{table.key}`). Key: {table.key_comment()}", 10),
        ]
    return "\n".join(lines) + "\n"


def _cadence(folder_tables: list[Table]) -> str:
    cadences = {table.cadence for table in folder_tables}
    if len(cadences) != 1:
        raise ValueError(f"{folder_tables[0].folder}: one source block per folder needs one cadence, found {sorted(cadences)}")
    return cadences.pop()


def base_yaml(folder: str, folder_tables: list[Table]) -> str:
    lines = [YAML_MARK + "version: 2", "", "models:"]
    for table in folder_tables:
        inputs = ", ".join(item.strip("'") if item.startswith("'") else item for item in table.key_inputs())
        lines += [
            f"  - name: {table.base}",
            "    data_tests:",
            "      # Says how many rows the dedupe dropped. Each is an exact copy",
            "      # (duplicates_are_exact on the raw table), so this only reports.",
            "      # A raw table that never landed passes (tests/generic/).",
            "      - equal_rowcount_to_raw:",
            "          arguments:",
            f"            compare_model: source('{folder}', '{table.table}')",
            "          config:",
            "            severity: warn",
            "    description: >",
            _folded(
                f"{table.title}, every row, keyed and deduped (decision 40), the layer's own columns under dlt's "
                f"names. {_held_back(table.entry)} "
                + (
                    f"A lookup beside stg_{folder}__{table.type}'s rows, which carry its ids; no union reads it."
                    if table.lookup
                    else f"{table.shape.union} reads it through stg_{folder}__{table.type}."
                ),
                6,
            ),
            "    columns:",
            f"      - name: {table.key_column}",
            "        description: >",
            _folded(
                f"The row's key (decision 40): dbt_utils.generate_surrogate_key over {inputs}, the registry key "
                "first and then the fields measured unique for this layer.",
                10,
            ),
            "        data_tests: [not_null, unique]",
        ]
    return "\n".join(lines) + "\n"


# --- staging models -------------------------------------------------------------------------------------------


def _name(entry: dict) -> str:
    """The `name` column: the registry's `name_field`, else its `name_constant`, else null."""
    if entry.get("name_field"):
        return f"cast({column(entry['name_field'])} as varchar) as name"
    if entry.get("name_constant"):
        line = f"cast({_sql_text(entry['name_constant'])} as varchar) as name"
        if len(line) + 5 <= 80:  # indent, and the comma after it
            return line
        # LT05: a long constant is cut at spaces into pieces joined with ||, each piece keeping its space.
        pieces, piece = [], ""
        for word in entry["name_constant"].split(" "):
            candidate = f"{piece} {word}" if piece else word
            if piece and len(_sql_text(candidate + " ")) > 60:
                pieces.append(piece + " ")
                piece = word
            else:
                piece = candidate
        pieces.append(piece)
        joined = "\n        || ".join(_sql_text(text) for text in pieces)
        return f"cast(\n        {joined} as varchar\n    ) as name"
    return "cast(null as varchar) as name"


def _conformed(table: Table) -> list[str]:
    entry = table.entry
    if table.type == "trail_lines":
        return [_name(entry)]
    if table.type == "points_of_interest":
        category = f"cast({column(entry['type_field'])} as varchar)" if entry.get("type_field") else "cast(null as varchar)"
        id_field = entry.get("id_field")
        if id_field and column(id_field).strip('"') not in ROW_IDS:
            source_id = f"cast({column(id_field)} as varchar)"
        else:
            source_id = f"cast({table.base_key_column} as varchar)"
        return [_name(entry), f"{category} as category", f"{source_id} as source_id"]
    if table.type == "places":
        category = (
            f"cast({column(entry['category_field'])} as varchar)" if entry.get("category_field") else "cast(null as varchar)"
        )
        return [_name(entry), f"{category} as category"]
    if table.type == "elevation":
        source = entry.get("elevation_source") or ""
        if source.startswith("field "):
            return [f"cast({column(source.removeprefix('field ').strip())} as varchar) as published_elevation"]
        if source == "geometry Z":
            return ["cast(null as varchar) as published_elevation"]
        raise ValueError(f"{table.key}: elevation_source {source!r} is neither 'field <name>' nor 'geometry Z'")
    if not table.shape.geometry:
        return _content_conformed(table)
    raise ValueError(f"{table.key}: no staging shape for type {table.type}")


def content_columns(table: Table) -> dict[str, str | None]:
    """A content table's conformed columns: CONTENT_COLUMNS for its reader, an NPS list's by its endpoint."""
    if table.reader == "NpsContent":
        path = table.entry["url"].rstrip("/").split("/api/v1/", 1)[-1]
        found = NPS_COLUMNS.get((table.type, path))
        if found is None:
            raise ValueError(f"{table.key}: no NPS_COLUMNS row for {table.type} from {path!r}")
        return found
    return CONTENT_COLUMNS[(table.type, table.reader)]


def _content_conformed(table: Table) -> list[str]:
    lines = []
    for name, field in content_columns(table).items():
        if field is None:
            lines.append(f"cast(null as varchar) as {name}")
        elif " " in field:
            raw, path = field.split(" ", 1)
            lines.append(f"json_extract_string({column(raw)}, '{path}') as {name}")
        else:
            lines.append(f"cast({column(field)} as varchar) as {name}")
    return lines


def stg_sql(folder: str, type_: str, type_tables: list[Table]) -> str:
    shape = SHAPES[type_]
    if not shape.geometry:
        return _content_stg_sql(folder, type_, type_tables)
    head = _comment(
        f"The {folder}/ folder's {type_.replace('_', ' ')} layers, conformed to {shape.union}'s columns: each "
        "layer's rename to the union's names and its key, nothing filtered (decision 40; a club's review gate is "
        "an intermediate's). The layer's own columns ride whole in `properties`, under dlt's names, so a rule "
        "downstream reads a field by the name its registry row gives it: json_merge_patch drops a member a "
        "patch sets to null, so `properties` is the base row without the geometry that travels beside it."
    )
    branches = []
    for table in type_tables:
        conformed = "".join(f"\n    {line}," for line in _conformed(table))
        key = shape.key_column if table.base_key_column == shape.key_column else f"{table.base_key_column} as {shape.key_column}"
        branches.append(
            f"""select
    '{table.key}' as source_key,
    '{folder}' as club,
    {key},{conformed}
    geom,
    json_merge_patch(
        to_json({table.base}),
        '{{"geom": null}}'
    ) as properties,
    _loaded_at
from {{{{ ref('{table.base}') }}}}"""
        )
    return SQL_MARK + head + "\n" + "\nunion all by name\n".join(branches) + "\n"


def _patch_lines(members: str) -> list[str]:
    """A JSON object literal, `'{...}'`, cut at its commas into lines SQLFluff's 80 columns hold (`||` joined)."""
    if not members:
        return ["'{}'"]
    parts = members.split(", ")
    lines, line = [], ""
    for part in parts:
        candidate = f"{line}, {part}" if line else part
        if line and len(candidate) > 56:
            lines.append(line + ",")
            line = part
        else:
            line = candidate
    lines.append(line)
    if len(lines) == 1:
        return ["'{" + lines[0] + "}'"]
    quoted = ["'{" + lines[0] + " '"] + [f"|| '{text} '" for text in lines[1:-1]] + [f"|| '{lines[-1]}}}'"]
    return quoted


def _content_stg_sql(folder: str, type_: str, type_tables: list[Table]) -> str:
    """A content type's staging model: each table's rename to the union's columns and its key, as text."""
    shape = SHAPES[type_]
    head = _comment(
        f"The {folder}/ folder's {type_.replace('_', ' ')} sources, conformed to {shape.union}'s columns: each "
        "source's rename to the union's names and its key, nothing filtered (decision 40; a club's review gate is "
        "an intermediate's). The source's own columns ride in `properties`, under dlt's names, all but its prose: "
        "json_merge_patch drops each member the patch sets to null, so a body, an episode's notes or a page's "
        "wikitext stops at the base model (decision 55)."
    )
    branches = []
    for table in type_tables:
        conformed = "".join(f"\n    {line}," for line in _conformed(table))
        prose = ", ".join(f'"{column(name).strip(chr(34))}": null' for name in CONTENT_PROSE.get(table.reader, ()))
        patch = "\n".join(f"        {line}" for line in _patch_lines(prose))
        branches.append(
            f"""select
    '{table.key}' as source_key,
    '{folder}' as club,
    {shape.key_column},{conformed}
    json_merge_patch(
        to_json({table.base}),
{patch}
    ) as properties,
    _loaded_at
from {{{{ ref('{table.base}') }}}}"""
        )
    return SQL_MARK + head + "\n" + "\nunion all by name\n".join(branches) + "\n"


def models_yaml(folder: str, by_type: dict[str, list[Table]]) -> str:
    lines = [YAML_MARK + "version: 2", "", "models:"]
    for type_, type_tables in sorted(by_type.items()):
        shape = SHAPES[type_]
        keys = ", ".join(f"`{table.key}`" for table in type_tables)
        lines += [
            f"  - name: stg_{folder}__{type_}",
            "    description: >",
            _folded(
                f"The {folder}/ folder's {type_.replace('_', ' ')} layers ({keys}), one row per base row, renamed to "
                f"{shape.union}'s columns, with each layer's own columns in `properties`.",
                6,
            ),
            "    columns:",
            f"      - name: {shape.key_column}",
            "        description: The base model's key, carried.",
            "        data_tests: [not_null, unique]",
        ]
    return "\n".join(lines) + "\n"


# --- unions ---------------------------------------------------------------------------------------------------


def union_sql(type_: str, staging_models: list[str]) -> str:
    shape = SHAPES[type_]
    geometry = ["geom"] if shape.geometry else []
    columns = [
        "source_key",
        "club",
        shape.key_column,
        *(name for name, _ in shape.columns),
        *geometry,
        "properties",
        "_loaded_at",
    ]
    what = "registered layers" if shape.geometry else "registered feeds, APIs and WordPress and wiki sources"
    head = _comment(
        f"Every {type_.replace('_', ' ')} row of the clubs' {what} that pipeline/make_dbt_staging.py "
        "stages, one row each, unfiltered: a `union all by name` of every stg_<folder>__"
        f"{type_} it writes. The branch list is the registry's, written by the generator from sources.json and the "
        "extract's club folders, so a layer registered later joins by running it again. Nothing here is filtered "
        "for publication: whatever reads it keeps int_sources__publication's verdict, the one home of may_publish."
    )
    select = ",\n    ".join(columns)
    branches = [f"select\n    {select}\nfrom {{{{ ref('{model}') }}}}" for model in staging_models]
    return SQL_MARK + "{{ config(materialized='table') }}\n" + head + "\n" + "\nunion all by name\n".join(branches) + "\n"


def union_yaml(type_: str, type_tables: list[Table]) -> str:
    shape = SHAPES[type_]
    if shape.geometry:
        description = (
            f"Every {type_.replace('_', ' ')} row of the {len(type_tables)} registered layers "
            f"pipeline/make_dbt_staging.py stages, unioned by name: {shape.row}. Each row carries its layer's "
            "registry key, the club folder that extracted it, the base model's key, the conformed columns below, "
            "its geometry as landed and its layer's own columns as `properties`. Unfiltered: whatever reads it keeps "
            "int_sources__publication's verdict."
        )
        region_test = [
            "    data_tests:",
            "      # The lon/lat swap test, against the box each source's rows are held",
            "      # to (macros/generated_regions.sql, read by",
            "      # macros/lands_outside_its_region.sql).",
            "      - lands_in_the_region_its_source_publishes_in:",
            "          arguments:",
            "            geometry: geom",
        ]
    else:
        description = (
            f"Every {type_.replace('_', ' ')} row of the {len(type_tables)} registered sources "
            f"pipeline/make_dbt_staging.py stages for this type (decision 54 wave 3), unioned by name: {shape.row}. "
            "Each row carries its source's registry key, the club folder that extracted it, the base model's key, "
            "the conformed columns below and its source's own columns, prose left out, as `properties`. No "
            "geometry: a row is placed, where it is placed at all, by its own fields in `properties`. Unfiltered: "
            "whatever reads it keeps int_sources__publication's verdict."
        )
        region_test = []
    lines = [
        YAML_MARK + "version: 2",
        "",
        "models:",
        f"  - name: {shape.union}",
        "    description: >",
        _folded(description, 6),
        *region_test,
        "    columns:",
        f"      - name: {shape.key_column}",
        "        description: The base model's key, carried; unique across the union because the registry key is its first input.",
        "        data_tests: [not_null, unique]",
        "      - name: source_key",
        "        description: The layer's sources.json key.",
        "        data_tests:",
        "          - not_null",
        "          - relationships:",
        "              arguments:",
        "                to: ref('stg_registry__sources')",
        "                field: source_key",
        "      - name: club",
        "        description: The extract folder that landed the row (trail_orgs.json's slug, `-` written `_`).",
        "        data_tests: [not_null]",
    ]
    for name, description in shape.columns:
        lines += [f"      - name: {name}", "        description: >", _folded(description, 10)]
    if shape.geometry:
        lines += [
            "      - name: geom",
            "        description: The feature's geometry as the layer published it, in OGC:CRS84, with a Z where the layer's vertices carry one.",
            "      - name: properties",
            "        description: The base row's own columns, under dlt's names, as JSON, the geometry left out.",
        ]
    else:
        lines += [
            "      - name: properties",
            "        description: The base row's own columns, under dlt's names, as JSON, its prose left out (decision 55).",
        ]
    lines += [
        "      - name: _loaded_at",
        "        description: When the extract landed the row (dlt's load stamp).",
    ]
    return "\n".join(lines) + "\n"


def hand_set_regions() -> set[str]:
    """The source keys macros/lands_outside_its_region.sql's own `regions` map lists: a box somebody set by hand."""
    import re

    text = (DBT / "macros" / "lands_outside_its_region.sql").read_text()
    block = re.search(r"\{%-?\s*set regions = \{(.*?)\}\s*-?%\}", text, re.S)
    return set(re.findall(r"'([a-z0-9_]+)':", block.group(1))) if block else set()


def regions_macro(all_tables: list[Table]) -> str:
    by_hand = hand_set_regions()
    keys = sorted(
        {
            table.key
            for table in all_tables
            if table.key not in by_hand and table.type not in REGIONS_DECIDED_BY_HAND and table.shape.geometry
        }
    )
    cases = "\n".join(f"    when {{{{ column }}}} = '{key}' then '{DEFAULT_REGION}'" for key in keys)
    return (
        JINJA_MARK
        + """{#-
    The region box each source pipeline/make_dbt_staging.py stages is held
    to, as CASE branches on its key for macros/lands_outside_its_region.sql:
    us_and_territories for every one the macro's own `regions` map does not
    already list, the widest box that still catches a swapped United States
    point. @unvalidated as a fit, and never set from a server's extent (the
    generator's DEFAULT_REGION says why); each source's row of
    int_<type>__source_extents names the narrowest box its vertices fit.
    SQL rather than a returned dict, so SQLFluff's jinja templater renders
    it as dbt does.
-#}
{% macro generated_region_cases(column) -%}
"""
        + cases
        + """
{%- endmacro %}
"""
    )


# --- the run --------------------------------------------------------------------------------------------------


def render() -> dict[Path, str]:
    """Every file this writes, by path, from the registry and the extract's folders as they stand."""
    all_tables = tables()
    files: dict[Path, str] = {}
    by_folder: dict[str, list[Table]] = {}
    for table in all_tables:
        by_folder.setdefault(table.folder, []).append(table)
    staging_by_type: dict[str, list[str]] = {}
    tables_by_type: dict[str, list[Table]] = {}
    for folder, folder_tables in sorted(by_folder.items()):
        root = STAGING / folder
        # A shared resource is one raw table: its source and base come from the type that extracts it.
        owned = [table for table in folder_tables if table.shared_from is None]
        files[root / f"_{folder}__generated__sources.yml"] = sources_yaml(folder, owned)
        files[root / "base" / f"_{folder}__generated__base.yml"] = base_yaml(folder, owned)
        by_type: dict[str, list[Table]] = {}
        for table in folder_tables:
            if table.shared_from is None:
                files[root / "base" / f"{table.base}.sql"] = base_sql(table)
            if not table.lookup:
                by_type.setdefault(table.type, []).append(table)
        for type_, type_tables in sorted(by_type.items()):
            files[root / f"stg_{folder}__{type_}.sql"] = stg_sql(folder, type_, type_tables)
            staging_by_type.setdefault(type_, []).append(f"stg_{folder}__{type_}")
            tables_by_type.setdefault(type_, []).extend(type_tables)
        files[root / f"_{folder}__generated__models.yml"] = models_yaml(folder, by_type)
    for type_, staging_models in sorted(staging_by_type.items()):
        shape = SHAPES[type_]
        files[INTERMEDIATE / type_ / f"{shape.union}.sql"] = union_sql(type_, staging_models)
        files[INTERMEDIATE / type_ / f"_{type_}__generated__intermediate.yml"] = union_yaml(type_, tables_by_type[type_])
    files[REGIONS_MACRO] = regions_macro(all_tables)
    # SQLFluff's LT05 holds a model's every line to 80 and runs ten minutes into the dbt job: fail here instead.
    long = [
        f"{path.relative_to(PIPELINE)}:{number}"
        for path, text in files.items()
        if path.suffix == ".sql" and path.parent.name != "macros"
        for number, line in enumerate(text.split("\n"), 1)
        if len(line) > 80
    ]
    if long:
        raise ValueError("generated lines over SQLFluff's 80 columns: " + ", ".join(long))
    return files


def generated_on_disk() -> set[Path]:
    """Every file under dbt/ that this generator wrote, by its first line."""
    found = set()
    for path in [*MODELS.rglob("*.sql"), *MODELS.rglob("*.yml"), REGIONS_MACRO]:
        if path.is_file() and GENERATED in path.read_text().split("\n", 1)[0]:
            found.add(path)
    return found


def differences(files: dict[Path, str]) -> list[str]:
    problems = []
    for path, text in sorted(files.items()):
        if not path.exists():
            problems.append(f"missing: {path.relative_to(PIPELINE)}")
        elif path.read_text() != text:
            problems.append(f"differs: {path.relative_to(PIPELINE)}")
        elif GENERATED not in path.read_text().split("\n", 1)[0]:
            problems.append(f"hand-written file in the way: {path.relative_to(PIPELINE)}")
    for path in sorted(generated_on_disk() - set(files)):
        problems.append(f"stale: {path.relative_to(PIPELINE)}")
    return problems


def write(files: dict[Path, str]) -> None:
    for path, text in files.items():
        if path.exists() and GENERATED not in path.read_text().split("\n", 1)[0]:
            raise FileExistsError(f"{path}: a hand-written file is where a generated one goes; nothing written")
    for path in generated_on_disk() - set(files):
        path.unlink()
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 naming each file that would change")
    args = parser.parse_args(argv)
    files = render()
    if args.check:
        problems = differences(files)
        for problem in problems:
            print(problem)
        return 1 if problems else 0
    write(files)
    print(f"{len(files)} generated files written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
