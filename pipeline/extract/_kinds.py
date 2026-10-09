"""One builder per source kind: what a club file calls to declare a resource.

Every builder takes a KEY and never a URL. The URL, the field names, the
filter and the change marker come from the key's sources.json entry, so a club
file cannot fetch an upstream the registry does not register, and an upstream
has one home (pipeline/ELT.md, "One home: sources.json, trail_orgs.json, the
club file").

Nothing here imports dlt. A builder yields plain rows and says what its columns
are; extract/_run.py wraps each one in a dlt resource. That keeps the layout
test, which imports every club file, free of the run machinery, and keeps one
place deciding the dlt settings every resource shares.

The kinds built so far for stage 2 (#1793 — Rebuild the data platform as dlt → dbt):

    arcgis_layer(key)       an ArcGIS FeatureServer or MapServer layer
    socrata_dataset(key)    a Socrata dataset, under the entry's own `where`
    wordpress_posts(key)    one WordPress category's posts (NYNJTC's Trail Alerts)
    wordpress_terms(key, t) that site's taxonomy terms, daily, for dbt to resolve
    guide_pages(key)        a guide published as web pages, one row per section
    published_hikes(key)    the Hike Finder export, one row per hike, GPX as served
    club_pdf(key)           a club's PDF, one row per row its lib/club_pdfs.py parser reads
    opentrail_feed()        opentrail.org's A.T. waypoints, comments left out (no registry row)
    hydrography_watch(key)  the usgs_3dhp watch: 3DHP's work units at five probes on the trail
    bucket_listing(key)     a public S3 bucket's objects under one prefix (3DEP's tiles, NHD's GeoPackages)
    nws_alerts()            every active NWS alert, read in full each hour (no registry row)
    conditions_query(key)   one of OurHike's own conditions artifacts, from Postgres, through the bake's own query
    reviewed_input(key)     a registry entry whose rows a person reviews into a
                            file in git (ATC's Trail Updates), loaded from that file
    reviewed_file(path)     a reviewed pipeline/reference/ file with no registry
                            row of its own (water_distance.json)
    reviewed_dir(path)      a folder of reviewed files, one row per file (a
                            club's challenges)
    podcast_feed(key)       a podcast's RSS feed, one row per episode
    geofabrik_extracts(key) OSM's state extracts kept as files in the raw store, one manifest
                            row each, never the bytes (extract/_geofabrik.py)
    feed_notices(key)       a club's RSS or Atom notices, one row per item (extract/_notices.py)
    page_notice(key)        a club's notice page or PDF, one notice per page (extract/_notices.py)
    catalogue_row()         the club's own trail_orgs.json row, which discover() makes for every
                            managing club (decision 88)
    atc_trail_update_pages(key)
                            ATC's Trail Updates read off their website, one row
                            per update their trail-updates sitemap lists, as
                            lib/atc_scrape.py parses its page
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import tempfile
import time
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from resource import RUSAGE_SELF, getrusage
from urllib.parse import urljoin, urlparse

import psycopg
import requests
from psycopg.rows import dict_row

import export_conditions
from check_freshness import CORRIDOR_PROBES
from extract._contract import (
    EXTRACT_DIR,
    PIPELINE_DIR,
    TRAIL_ORGS_PATH,
    Carried,
    Incomplete,
    Resource,
    Unavailable,
    read_club_file,
    slug_for_folder,
)

# Decision 53's notice readers, in a module of their own for this file's
# length. They are builders like the rest, so a club file imports them from
# here; extract/_notices.py's docstring says why it cannot import this file.
from extract._notices import (  # noqa: F401
    DEFAULT_HOST_GAP_SECONDS,
    FeedNotices,
    PageNotice,
    feed_notices,
    page_notice,
    polite,
    query_refused,
    refuse_other_hosts,
)
from fetch_atc_updates import TOLERATED_PARSE_FAILURES as ATC_TOLERATED_PARSE_FAILURES
from fetch_club_pdfs import extract_page_texts
from fetch_elevation import TILE_URL_TEMPLATE as DEM_TILE_URL_TEMPLATE
from fetch_hikefinder import sign_in as hikefinder_sign_in
from fetch_opentrail import API_URL as OPENTRAIL_API_URL
from fetch_opentrail import strip_comments as strip_opentrail_comments
from lib.arcgis import PAGE_SIZE as ARCGIS_PAGE_SIZE
from lib.arcgis import feature_object_id, iter_layer_pages, layer_count
from lib.atc_scrape import parse_update as parse_atc_update
from lib.atc_scrape import update_url as atc_update_url
from lib.club_pdfs import PARSERS as CLUB_PDF_PARSERS
from lib.freshness_state import Freshness, compare_marker
from lib.hikefinder import DETAIL_PATH as HIKEFINDER_DETAIL_PATH
from lib.hikefinder import GPX_PATH as HIKEFINDER_GPX_PATH
from lib.hikefinder import LISTING_PATH as HIKEFINDER_LISTING_PATH
from lib.hikefinder import as_cache_entry as as_hike_row
from lib.hikefinder import listing_count as hikefinder_listing_count
from lib.hikefinder import listing_ids as hikefinder_listing_ids
from lib.hikefinder import parse_gpx, parse_hike
from lib.http_retry import DEFAULT_BACKOFF_SECONDS, request_with_retry
from lib.nhd import NHD_GPKG_URL
from lib.nws_alerts import ACCEPT as NWS_ACCEPT
from lib.nws_alerts import ALERTS_URL as NWS_ALERTS_URL
from lib.nws_alerts import check_response as check_nws_response
from lib.nynjtc_long_path_guide import parse_index as parse_guide_index
from lib.nynjtc_long_path_guide import parse_section as parse_guide_section
from lib.socrata import dataset_url, fetch_dataset_geojson
from lib.source_registry import PODCAST_FEED, load_registry, source_kind
from lib.user_agent import USER_AGENT

REGISTRY_PATH = PIPELINE_DIR / "sources.json"
REFERENCE_DIR = PIPELINE_DIR / "reference"

# Fields that name or reach a person, which never load, whatever the licence
# (ELT.md, "Who may publish", rule 8): dropped inside the resource, before dlt
# sees the row, so no copy exists in the raw store to leak; never filtered in
# dbt. Matched case-insensitively against each layer's own field names.
#
# The names the coverage audit read off live layers (2026-10-01): Forest
# Ranger Contact's RANGER, PHONE_CELL, PHONE_ALT, EMAIL, SUPERVISOR and
# SUPERVIS_1, and the Central Iowa Trail Association status API's
# updateByDisplay. The statewide Forest Ranger line, 833-NYS-RANGERS, is
# DEC's published number for an emergency in the backcountry, not a person's:
# it belongs in nysdec's catalogue row, its trail_orgs.json row, rather than
# in a layer, and adding it there is a reviewed change to that file, not made
# yet (this note sat in nysdec/org.py's docstring until decision 88).
#
# A denylist is only as complete as the layers somebody has read: a person
# field under another name loads until its name is added here, which is why a
# new registry row is reviewed field by field.
#
# ArcGIS editor tracking's four names hold the account that created or last
# edited each row, and an account is a person's or names one. Added
# 2026-10-03, when a metadata read of 44 of the 45 registered ArcGIS layers
# found 15 carrying them, and loading them: Creator and Editor on 10 of ATC's
# 12 layers; created_user and last_edited_user on oprhp_park_polygons,
# nj_statewide_trails, utah_sgid_trails, ncta_trail and
# duluth_superior_hiking_trail. (massgis_long_distance_trails was not read:
# its host's robots.txt answered 502.) ArcgisLayer also drops whatever names
# a layer's own `editFieldsInfo` gives, and a layer whose person field has an
# ordinary name, such as a `source` holding surveyors' names, lists it in the
# `person_fields` of its sources.json row.
PERSON_FIELDS = frozenset(
    name.lower()
    for name in (
        "RANGER",
        "PHONE_CELL",
        "PHONE_ALT",
        "EMAIL",
        "SUPERVISOR",
        "SUPERVIS_1",
        "updateByDisplay",
        "Creator",
        "Editor",
        "created_user",
        "last_edited_user",
    )
)

# The backstop for a person field nobody has named yet, such as next month's
# new staff column: an ArcGIS field whose name reads as a person's is left out
# unless its sources.json row clears it in `not_person_fields` (PASDA's
# `LastEdit_1`, say, if it ever arrives as text). Matched against the name
# split into words (_name_words), so `LastEdBy` is read as `last_ed_by` and
# `Contact Email` as `contact_email`. Dropped and printed, never a failed
# run: a false match costs one column until somebody clears it, and a missed
# one ships a person.
# @unvalidated: the word list was drafted for decision 54 on 2026-10-03 from
# the names seen so far, not from a survey of field names. What would settle
# it is the names a few monthly runs print, read for false matches and misses.
#
# `manager`, `superintendent`, `steward` and `surveyor` were added, and `user`
# matched at the end of a run-together word (NPS's `CREATEUSER`, `EDITUSER`),
# for review finding EXD-3 of PR #1805: PA DCNR's park layer loaded a
# `MANAGER` whose values have the shape of people's names (61 distinct over
# 125 parks, 123 with a space, none naming a park, region or bureau: the
# review counted them and read no value), and its row now names it in
# `person_fields`. In the 167 live field lists make_dbt_fixtures.py copies,
# `manager` matches six other columns. Three rows record theirs as agencies
# and clear it in `not_person_fields` (cotrex_trailheads, pcta_trailheads,
# ridgetrail_campsites), as mohonk_trails does the `Manager` its staging model
# reads; the other three are left out until a person reads them
# (nj_open_space_points_of_interest's LAND_MANAGER, portland_parks_trails'
# Manager, amc_trailheads_and_parking's Tr_Manager, whose row lists 78 of its
# 106 values). `steward`, `superintendent` and `surveyor` match none of them.
#
# `author` and `authors` were added for review finding SEC-2 of PR #1805: a
# WordPress theme's or plugin's field naming a post's author, which a site can
# add after its row was read field by field. Two registered sites already serve
# one (ridgetrail_curated_adventures' `author_info`, gmc_trail_alerts'
# `uagb_author_info`, both in their rows' `person_fields`), and PublishPress
# Authors serves `authors` (Reasoned from that plugin's REST field; no
# registered site was read for it). Measured 2026-10-06: the word matches no
# column fixture mode lands from make_dbt_fixtures.py's files, and no reader
# that asks this backstop lands a column a model reads by that name (the Hike
# Finder's `author`, which publishes, is PublishedHikes', which names its own).
#
# WIDENED 2026-10-09, when decision 54's wave 6 registered two layers whose
# person fields these words missed: D&L Corridor's trailheads name their
# inspectors in `updatedBy`, and Montour Trail's access areas carry editor
# accounts in `MODIFIED_BY` and the locator in `LocationBy`. Both rows name
# them in `person_fields`, so nothing reached a store; a layer registered
# later has only this pattern. PR #1805's security review the same night ran
# this pattern over 50 names and listed 23 more that load (`LastModifiedBy`,
# `reviewed_by`, `GPS_By`, `RangerName`, `first_name`, `volunteer`, `mobile`
# and others). Esri's own editor-tracking names, `created_user` and
# `last_edited_user` (ArcGIS Pro's Enable Editor Tracking defaults, and the
# REST API's editFieldsInfo example, both read 2026-10-09), are PERSON_FIELDS
# entries already. Each alternative after the first two lines answers one of
# those names:
#   - who did something, a word ending in `by`, separate or run together
#     (`updatedBy`, `MODIFIED_BY`, `LocationBy`, `GPS_By`, `Round1QAQCBy`),
#     and `assigned_to`. It also reads `nearby`, `lobby` and `baby_changing`
#     as a person's, none of them a field any registered layer is recorded as
#     carrying;
#   - Esri's two names cut to a shapefile's ten characters, `created_us` and
#     `last_edite`, which four registry rows already list by hand;
#   - a person's own name, `first_name`, `LastName`, `full_name`;
#   - a role run into its name (`OWNERNAME`, `OWNERNME1`, `RangerName`), or
#     ending the name (`INSPECTOR`, `TrailAdopter`, `volunteers`,
#     `COLLECTOR`, `DataEntryPerson`, and the Buckeye Trail's "Section
#     supervisor", a volunteer's name its parser never reads), but not
#     followed by another word, so `RANGER_DISTRICT` and `reporter_type` load;
#   - `contact`, `phone` and `email` anywhere in a run-together word
#     (`entityphone`, `MGRPHONE`, `contacts`), a phone or fax number run
#     together (`TELNO`, `FAXNUMBER`), and `mobile` or `cell` as the name's
#     last word, so PA DCNR's `MOBILE_FAC` and a grid's `cell_size` still load.
#
# Measured 2026-10-09 against the 176 full live field lists
# make_dbt_fixtures.py copies (CLUB_TRAIL_LINE_FIELDS, CLUB_POINT_FIXTURES)
# and every other fixture layer: the widened pattern reads 21 more of the 124
# distinct names the registry's rows list in `person_fields` as a person's
# (each listed there by hand already, so on those rows nothing changes), and
# leaves out 12 columns it did not before, on 12 layers. Eight of those name
# a place or a body, and each one's row clears it in `not_person_fields`:
# four that a model reads (nynjtc_long_path's `Maintainer`, 'NYNJTC' on all
# 43 rows; ugrc_state_park_points' `full_name`, its name and key; and
# oprd_hunting_areas' `FULL_NAME` and nps_seki_closures' `FullName`, which
# seeds/notice_source_fields.csv reads as each notice's title), and four
# whose rows record what they hold (patc_trails_master's `Maintainer`,
# nps_points_of_interest's and nps_trail_of_tears_nht's `MAINTAINER`,
# usace_mobile_trails' `managedBy`). The other four are left out until a
# person reads them: nps_anza_nht's and usfws_trail_segments' `MAINTAINER`,
# nc_state_parks_points' `FullName` and montour_trail_access_areas'
# `AssetMaintainer`. No model reads any of the four, nor NWS's `replacedBy`,
# which the `by` rule would leave out of an alert that carries one, and which
# has no sources.json row to clear it in.
# @unvalidated, as the first word list was: what would settle it is the
# "left out ... person-shaped names" lines the first monthly and notices runs
# print, read for false matches on layers whose field lists no fixture records.
PERSON_SHAPED = re.compile(
    r"(^|_)(user|user_?name|editor|edited_?by|created_?by|creator|last_?ed_?by|last_?edit(ed|or)?(_?by)?"
    r"|owner|phone|telephone|tel|fax|email|e_?mail|contact|manager|superintendent|steward|surveyor|authors?)($|_|\d)"
    r"|[a-z]user($|_|\d)"
    r"|(^|_)[a-z]+_?by($|_|\d)"
    r"|(^|_)assigned_?to($|_|\d)"
    r"|(^|_)(created_?us|last_?edite)($|_|\d)"
    r"|(^|_)(first|last|full)_?name($|_|\d)"
    r"|(owner|creator|editor|author|user|manager|steward|surveyor|ranger|inspector|reporter|submitter|overseer"
    r"|adopter|volunteer|maintainer|collector|supervisor|person)_?n(a)?me"
    r"|(ranger|inspector|reporter|submitter|overseer|adopter|volunteer|maintainer|collector|supervisor)s?($|\d)"
    r"|person($|\d)"
    r"|contact|phone|email"
    r"|(^|_)(tel|fax)_?(no|num|nbr|number)($|_|\d)"
    r"|(^|_)(mobile|cell)($|\d)"
)

# Field types whose values are never a person's name, whatever the field is
# called: ArcGIS's ids and its dates. So editor tracking's `last_edited_date`
# loads while `last_edited_user` does not, and so does a date that happens to
# be named like an editor.
NEVER_PERSON_TYPES = frozenset(
    {
        "esriFieldTypeOID",
        "esriFieldTypeGlobalID",
        "esriFieldTypeGUID",
        "esriFieldTypeDate",
        "esriFieldTypeDateOnly",
        "esriFieldTypeTimeOnly",
        "esriFieldTypeTimestampOffset",
    }
)


def _name_words(name: str) -> str:
    """`LastEdBy` as `last_ed_by`, `Contact Email` as `contact_email`: the name split into words, so PERSON_SHAPED sees them.

    Split at each lower-to-upper step and at each run of characters that are neither a letter nor a digit (a space,
    a hyphen, a dot, an underscore, a `#`), then lower-cased. Before the second split, a name written with spaces,
    as KML ExtendedData, a QGIS GeoJSON export or a CSV header often writes one, read as one word: `Contact Email`,
    `E-mail` and `Phone Number` matched nothing and landed as dlt's `contact_email`, `e_mail` and `phone_number`
    (round-2 fix worker A of PR #1805 — dlt → dbt re-platform as one go/no-go change, 2026-10-06).
    """
    return re.sub(r"[\W_]+", "_", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)).lower()


@lru_cache(maxsize=1)
def _naming():
    from dlt.common.normalizers.naming.sql_ci_v1 import NamingConvention

    return NamingConvention()


@lru_cache(maxsize=8192)
def landed_name(name: str) -> str:
    """The column dlt lands an upstream field as: sql_ci_v1, the naming .dlt/config.toml and extract/_run.py set.

    `Contact Email` lands as `contact_email`, and so does `contact.email`. PersonRule compares a row's lists in
    this form as well as lower-cased, so a `person_fields` entry written as the column a person saw in the raw
    store matches the upstream's own spelling, and the other way round.
    """
    return _naming().normalize_identifier(name)


@lru_cache(maxsize=1024)
def _landed_names(names: frozenset[str]) -> frozenset[str]:
    return frozenset(landed_name(name) for name in names)


def _named_in(name: str, names: frozenset[str]) -> bool:
    """Whether `name` is one of `names` (each lower-cased), compared lower-cased or as dlt lands both (landed_name())."""
    return name.lower() in names or landed_name(name) in _landed_names(names)


#: The reason PersonRule gives for a name only PERSON_SHAPED left out, which each reader prints (report_shaped()).
SHAPED = "a person-shaped name"


@dataclass(frozen=True)
class PersonRule:
    """Which of an upstream's own field names never load: decision 59's rule, one home for every reader kind.

    ELT.md's rule 8 ("Who may publish"): a field that names or reaches a
    person never loads, and is left out inside the resource, before dlt sees
    the row. Every reader that lands fields it did not name asks this
    (PersonRuled); a reader that names every column it lands needs nothing.
    Review findings PY-1 and SEC-4 of PR #1805 (dlt → dbt re-platform as one
    go/no-go change) found the rule in seven copies, five of them different:
    Socrata and opentrail read PERSON_FIELDS alone, so a name in a Socrata
    row's `person_fields` kept loading; NPS content compared the row's names
    in exact case; My Maps' ExtendedData had no rule at all.

    In order, every name compared lower-cased and also as the column dlt lands
    it (landed_name()), so `Contact Email` upstream and `contact_email` in a
    row's list are one name:
    1. PERSON_FIELDS, the row's own `person_fields` and the reader's
       `plumbing` (WordPress's WP_DROPPED) are always left out, whatever the
       row's `not_person_fields` says;
    2. PERSON_SHAPED, read against the name split into words (_name_words),
       leaves the rest out unless `not_person_fields` clears the name.

    `field_rules` is what extract/_run.py's definition_digest() keeps, so a
    name added to either list reads the upstream again on the next run,
    whether or not it moved.
    """

    person_fields: frozenset[str] = frozenset()
    not_person_fields: frozenset[str] = frozenset()
    plumbing: frozenset[str] = frozenset()

    @classmethod
    def of(cls, entry: dict | None, plumbing: frozenset[str] = frozenset()) -> PersonRule:
        """The rule a sources.json row sets, or PERSON_FIELDS and PERSON_SHAPED alone for a reader with no row."""
        entry = entry or {}
        return cls(
            person_fields=frozenset(name.lower() for name in entry.get("person_fields") or ()),
            not_person_fields=frozenset(name.lower() for name in entry.get("not_person_fields") or ()),
            plumbing=frozenset(name.lower() for name in plumbing),
        )

    @property
    def field_rules(self) -> dict[str, list[str]]:
        """The row's two lists, lower-cased and sorted: the shape definition_digest() has always kept."""
        return {"person_fields": sorted(self.person_fields), "not_person_fields": sorted(self.not_person_fields)}

    def listed(self, name: str) -> str | None:
        """The list that always leaves `name` out (step 1), or None."""
        if _named_in(name, PERSON_FIELDS):
            return "PERSON_FIELDS"
        if _named_in(name, self.person_fields):
            return "the row's person_fields"
        if _named_in(name, self.plumbing):
            return "the reader's plumbing"
        return None

    def shaped(self, name: str) -> bool:
        """Whether PERSON_SHAPED reads `name` as a person's and the row's `not_person_fields` does not clear it (step 2)."""
        return not _named_in(name, self.not_person_fields) and bool(PERSON_SHAPED.search(_name_words(name)))

    def left_out(self, names) -> dict[str, str]:
        """Every one of `names` that never loads, lower-cased, with the rule that leaves it out."""
        verdicts = {name.lower(): self.listed(name) or (SHAPED if self.shaped(name) else None) for name in names}
        return {name: reason for name, reason in verdicts.items() if reason}


def report_shaped(key: str, dropped: dict[str, str], names=None) -> None:
    """Print the names only PERSON_SHAPED left out, as the upstream spells them where `names` says, so a false match is
    seen and cleared in `not_person_fields`."""
    if shaped := sorted(name for name in (dropped if names is None else names) if dropped.get(name.lower()) == SHAPED):
        print(f"  {key}: left out {shaped}, person-shaped names its sources.json row does not clear in not_person_fields")


class PersonRuled:
    """A reader that lands fields it did not name: PersonRule decides which never load, and `field_rules` is its digest's.

    The rule comes from the resource's sources.json row (`entry`), or is
    PERSON_FIELDS and PERSON_SHAPED alone for a reader with no row (opentrail,
    NWS). `plumbing` is the kind's own always-dropped names.
    """

    plumbing: frozenset[str] = frozenset()

    @property
    def person_rule(self) -> PersonRule:
        try:
            entry = self.entry
        except (AttributeError, KeyError):
            entry = None
        return PersonRule.of(entry, self.plumbing)

    @property
    def field_rules(self) -> dict[str, list[str]]:
        return self.person_rule.field_rules

    def without_people(self, rows: list[dict]) -> list[dict]:
        """`rows` with every field the rule leaves out removed, the person-shaped names printed once for the read."""
        names = {name for row in rows for name in row}
        dropped = self.person_rule.left_out(names)
        report_shaped(self.key, dropped, names)
        return [{name: value for name, value in row.items() if name.lower() not in dropped} for row in rows]


def left_out_of_row(name: str, listed: set[str], dropped: dict[str, str], rule: PersonRule) -> bool:
    """Whether an ArcGIS row's property never lands: dropped from the field list, or, if the list never named it, by name.

    `listed` and `dropped` are the layer metadata's field names and
    ArcgisLayer.dropped_fields' verdicts on them, lower-cased. A property the
    metadata did not list is judged by the row's PersonRule alone, since
    without its type even a date named like an editor cannot be told from
    one: it is left out, which costs a column, never a person (review finding
    EXD-2).
    """
    lower = name.lower()
    if lower in dropped or rule.listed(name):
        return True
    return lower not in listed and rule.shaped(name)


# ArcGIS field types -> dlt data types. Hinting every column from the layer's
# own `fields` is what makes a column that is null on every row exist at all
# (dlt creates no column it never saw a value for; measured 2026-10-01, ELT.md
# "dlt configuration requirements"). Dates arrive as epoch milliseconds and
# stay integers here; the base model converts them.
ESRI_TYPES = {
    "esriFieldTypeOID": "bigint",
    "esriFieldTypeInteger": "bigint",
    "esriFieldTypeSmallInteger": "bigint",
    "esriFieldTypeBigInteger": "bigint",
    "esriFieldTypeDouble": "double",
    "esriFieldTypeSingle": "double",
    "esriFieldTypeString": "text",
    "esriFieldTypeGUID": "text",
    "esriFieldTypeGlobalID": "text",
    "esriFieldTypeDate": "bigint",
    "esriFieldTypeDateOnly": "text",
    "esriFieldTypeTimeOnly": "text",
    "esriFieldTypeTimestampOffset": "text",
}

# ArcGIS Online hosts its layers on servicesN.arcgis.com. Everything else is
# an ArcGIS Server somebody runs, whose ETags hash the response body and so
# never move when the features do (ELT.md, "The skip-unchanged check, by
# platform": identical ETags for identical bodies on DEC, USFS EDW and NPS,
# measured 2026-10-01).
AGOL_HOST = re.compile(r"^services\d*\.arcgis\.com$")

# How long a monthly layer's read waits out a server that stops answering,
# one pause per retry. lib/http_retry.py's default, (5, 30), failed the
# monthly lane twice on 2026-10-03 (refresh-reference.yml runs 37097625268
# and 37099504783): a gisservices.dec.ny.gov page timed out on all three
# attempts, once on DEC's primitive campsites and once on its fire towers.
# A count query on the campsites layer still got no answer within 90 s at
# about 05:14 UTC, then answered in 0.6 s at 05:19. This ladder pauses
# 1,055 s over six attempts, about 18 minutes before the timeouts, to outlast
# a hang that long. @unvalidated: picked from that one outage; how long
# upstream hangs really last, read from a few months of _extract_runs, would
# settle it. The hourly lanes keep the default, because a leg reads a club's
# resources one after another inside one read budget (_run.py's read_each),
# and a long wait on one would spend the others' time. Change checks keep it
# too: a failed check is UNKNOWN and the layer is read anyway.
MONTHLY_READ_BACKOFF_SECONDS = (5, 30, 120, 300, 600)


def session(entry: dict | None = None) -> requests.Session:
    """A session that names the project on every request, page and count included, and reads no other host's answer.

    Every request sends lib/user_agent.py's USER_AGENT, on every host, and
    never a browser's (decision 39): an operator should see who is asking from
    one line of their log, and a host that refuses our own named agent has
    refused us. An answer redirected to another host raises
    extract/_notices.py's RedirectRefused unless `entry`, the reader's
    sources.json row, names that host in `redirect_hosts` (refuse_other_hosts).
    """
    named = requests.Session()
    named.headers["User-Agent"] = USER_AGENT
    return refuse_other_hosts(named, entry)


def host_gated(entry: dict) -> requests.Session:
    """session(), every request held by extract/_notices.py's per-host gate: the row's `crawl_delay`, at least DEFAULT_HOST_GAP_SECONDS.

    One gate per host for the process, so two readers of one host keep the
    gap between them as well as within each (GATC's water PDF and its peaks
    page, both on a host asking `Crawl-delay: 10`; review finding EXD-4).
    """
    return polite(session(entry), max(float(entry.get("crawl_delay") or 0), DEFAULT_HOST_GAP_SECONDS))


@lru_cache(maxsize=4)
def _registry(path: Path) -> dict:
    return {entry["key"]: entry for entry in load_registry(path).get("sources", [])}


def registry_entry(key: str) -> dict:
    entry = _registry(REGISTRY_PATH).get(key)
    if entry is None:
        raise KeyError(f"{key} is not a sources.json key; a builder takes a registered key, never a URL")
    return entry


def _canonical(marker: dict) -> str:
    return json.dumps(marker, sort_keys=True)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_id_field(metadata: dict) -> str:
    """A layer's object id field: its metadata's `objectIdField`, else the field typed esriFieldTypeOID, else OBJECTID.

    Not every server names it in `objectIdField`: cicgis.org's
    `Chesapeake/CAJO/MapServer/0` leaves that key out, and its id field is
    `FID`, typed esriFieldTypeOID (measured 2026-10-03), so a bare "OBJECTID"
    fallback asked for statistics on a field the layer does not have. That
    particular layer refuses statistics on FID too ("Unable to complete
    operation", supportsStatistics false), so its check still answers
    UNKNOWN; a layer that does support them gets its fingerprint.
    """
    if metadata.get("objectIdField"):
        return metadata["objectIdField"]
    for field in metadata.get("fields") or []:
        if field.get("type") == "esriFieldTypeOID" and field.get("name"):
            return field["name"]
    return "OBJECTID"


# The names ArcGIS gives a layer's system length and area fields, lower-cased:
# file and enterprise geodatabases, hosted layers, SQL Server and Oracle.
LENGTH_FIELD_NAMES = ("shape_length", "shape__length", "shape.len", "shape.stlength()", "st_length(shape)")
AREA_FIELD_NAMES = ("shape_area", "shape__area", "shape.area", "shape.starea()", "st_area(shape)")


def geometry_measure_field(metadata: dict) -> str | None:
    """A layer's system length field, else its area field, else None (a point layer has neither).

    The metadata's `geometryProperties` names them where the server says;
    otherwise the field list is read for ArcGIS's own names. Length first,
    because a polygon layer that has both moves its length on a redraw too.
    """
    named = metadata.get("geometryProperties") or {}
    for key in ("shapeLengthFieldName", "shapeAreaFieldName"):
        if named.get(key):
            return named[key]
    fields = {(field.get("name") or "").lower(): field.get("name") for field in metadata.get("fields") or []}
    for names in (LENGTH_FIELD_NAMES, AREA_FIELD_NAMES):
        for name in names:
            if name in fields:
                return fields[name]
    return None


@dataclass(frozen=True)
class ArcgisLayer(PersonRuled, Resource):
    """An ArcGIS FeatureServer or MapServer layer, read whole through lib/arcgis.py's own loop.

    Pages come from `lib.arcgis.iter_layer_pages`, the loop every fetcher
    already uses - stop on an empty page, advance by rows returned, halve a
    page the server refuses (#1790) - and the read is held to the server's own
    `returnCountOnly` count afterwards (#1730). Not dlt's `rest_api` source,
    which ELT.md's first draft named: its OffsetPaginator steps by `limit`,
    and a second pager is what #1295 took out.
    """

    @property
    def entry(self) -> dict:
        return registry_entry(self.key)

    @property
    def url(self) -> str:
        return self.entry["url"].rstrip("/")

    @property
    def where(self) -> str:
        return self.entry.get("where") or "1=1"

    @property
    def platform(self) -> str:
        return "agol" if AGOL_HOST.match(urlparse(self.url).hostname or "") else "onprem"

    @property
    def may_be_empty(self) -> bool:
        return super().may_be_empty or bool(self.entry.get("may_be_empty"))

    @property
    def zero_proof(self) -> str:
        """The server's own `returnCountOnly` count under the entry's `where`, read after the pages (rows())."""
        return "the server's returnCountOnly count under the entry's where, read after the pages (lib/arcgis.py's layer_count())"

    @property
    def return_z(self) -> bool:
        """Whether the read keeps each vertex's Z: the entry's own `return_z`, off unless its row says so.

        A layer whose elevation is the reason it is registered, such as ATC's
        Z-enabled `ATX_Ratings` centerline, carries `return_z: true`, and its
        pages are read as Esri JSON with `returnZ=true`, because `f=geojson`
        drops Z (measured 2026-10-03; lib/arcgis.py's iter_layer_pages). The
        `geometry` column is still GeoJSON, its coordinates [x, y, z]. Off by
        default so that no layer registered before it changes shape.
        """
        return bool(self.entry.get("return_z"))

    @property
    def schema_contract(self) -> dict:
        """New columns are welcome; a column whose type changes is refused at normalize.

        Without `freeze`, a mistyped value splits into a variant column
        (`code__v_text`) that no staging model reads (ELT.md, measured on the
        #1363 spike).
        """
        return {"columns": "evolve", "data_type": "freeze"}

    def metadata(self, backoff: tuple[int, ...] = DEFAULT_BACKOFF_SECONDS) -> dict:
        return request_with_retry(self.url, session=session(), params={"f": "json"}, timeout=30, backoff=backoff).json()

    @property
    def read_backoff(self) -> tuple[int, ...]:
        """The retry pauses the layer's read uses: MONTHLY_READ_BACKOFF_SECONDS on the monthly lane, else the default."""
        return MONTHLY_READ_BACKOFF_SECONDS if self.cadence == "monthly" else DEFAULT_BACKOFF_SECONDS

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        try:
            if self.platform == "agol":
                return self._agol_check(recorded)
            return self._onprem_check(recorded)
        except (requests.RequestException, ValueError, KeyError) as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None

    def _agol_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """A conditional GET on the layer's metadata: a 304 means FRESH.

        On ArcGIS Online the layer document's validators move with the layer's
        data version: 304 on 30 of 30 layers repeated, and the layer's
        `Last-Modified` equals `editingInfo.lastEditDate` (measured
        2026-10-01, ELT.md). A user-maintained `Edit_Date` field is never the
        marker: ATC's shelters max at 2023-03-02 against a layer edit of
        2026-08-14.
        """
        headers = {}
        if recorded:
            if recorded.get("etag"):
                headers["If-None-Match"] = recorded["etag"]
            if recorded.get("last_modified"):
                headers["If-Modified-Since"] = recorded["last_modified"]
        response = request_with_retry(self.url, session=session(), params={"f": "json"}, headers=headers or None, timeout=30)
        if response.status_code == 304:
            return Freshness.FRESH, recorded
        marker = {"etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified")}
        if not marker["etag"] and not marker["last_modified"]:
            return Freshness.UNKNOWN, None
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def _onprem_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """One statistics query: count and max of the object id, plus the maintained date.

        A delete lowers the count and an add raises max(OID); the maintained
        date sees an edit in place (ELT.md). With no maintained date declared
        in the entry's `freshness.field`, an attribute-only edit moves none of
        those, so the answer is UNKNOWN and the layer is read in full every
        run: a false-stale costs a read, a false-fresh keeps a rerouted line
        on a phone. ELT.md's per-page conditional read, which would let such a
        layer skip, is not built yet.
        """
        date_field = (self.entry.get("freshness") or {}).get("field")
        if not date_field:
            return Freshness.UNKNOWN, None
        metadata = self.metadata()
        oid = object_id_field(metadata)
        statistics = [
            {"statisticType": "count", "onStatisticField": oid, "outStatisticFieldName": "n"},
            {"statisticType": "max", "onStatisticField": oid, "outStatisticFieldName": "max_oid"},
            {"statisticType": "max", "onStatisticField": date_field, "outStatisticFieldName": "max_date"},
        ]
        # The dlt skill's rule 4 fingerprint includes sum(Shape_Length): a redrawn
        # line or polygon moves it even where the maintained date is kept by hand
        # and nobody touched it (the trail-lines worker's finding, 2026-10-03).
        # Only when the layer has such a field; a point layer has none.
        measure = geometry_measure_field(metadata)
        if measure:
            statistics.append({"statisticType": "sum", "onStatisticField": measure, "outStatisticFieldName": "sum_measure"})
        response = request_with_retry(
            self.url + "/query",
            session=session(),
            params={"where": self.where, "outStatistics": json.dumps(statistics), "f": "json"},
            timeout=30,
        )
        features = response.json().get("features") or []
        if not features:
            return Freshness.UNKNOWN, None
        attributes = features[0].get("attributes") or {}
        marker = {name: attributes.get(name) for name in ("n", "max_oid", "max_date") + (("sum_measure",) if measure else ())}
        if any(value is None for value in marker.values()):
            return Freshness.UNKNOWN, None
        marker = {name: str(value) for name, value in marker.items()}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def dropped_fields(self, metadata: dict) -> dict[str, str]:
        """Every field of the layer that is never asked for or kept, lower-cased, with the rule that drops it.

        The row's PersonRule, with two things only a layer's metadata says:
        the creator and editor fields its own `editFieldsInfo` names are left
        out after the rule's lists (never its creation and edit dates, which
        load), and the PERSON_SHAPED backstop never reads an id or a date as a
        person (NEVER_PERSON_TYPES).
        """
        rule = self.person_rule
        tracking = metadata.get("editFieldsInfo") or {}
        tracked = {(tracking.get(role) or "").lower() for role in ("creatorField", "editorField")} - {""}
        dropped = {}
        for field in metadata.get("fields") or []:
            name = field.get("name")
            if not name:
                continue
            lower = name.lower()
            if reason := rule.listed(name):
                dropped[lower] = reason
            elif lower in tracked:
                dropped[lower] = "the layer's editFieldsInfo"
            elif field.get("type") not in NEVER_PERSON_TYPES and rule.shaped(name):
                dropped[lower] = SHAPED
        return dropped

    def column_hints(self) -> dict:
        hints = {"geometry": {"data_type": "json"}}
        metadata = self.metadata(self.read_backoff)
        dropped = self.dropped_fields(metadata)
        for field in metadata.get("fields") or []:
            name = field.get("name")
            data_type = ESRI_TYPES.get(field.get("type"))
            if name and data_type and name.lower() not in dropped:
                hints[name] = {"data_type": data_type}
        return hints

    def rows(self, proofs: dict[str, int]):
        """Every feature, as properties plus a `geometry` column, after the read is held to the server's count.

        The whole layer is read before the first row is yielded, so a short
        read raises before dlt has anything to normalize, and a failed page
        leaves nothing half-written. The pages are spooled to a temporary file
        on disk, one feature a line, rather than held in memory: monthly run 12
        (refresh-reference.yml 37180229539) lost its runner 43 minutes into the
        extract, after 15 silent minutes, with decision 54's largest layers to
        read (USGS's 176,566 populated places, Washington's 32,563 public-land
        polygons). That memory was the cause is Reasoned, not measured; the
        line each monthly layer now prints with its peak RSS settles it. A
        read an edit may have shifted is read again, once (`_read_into`).
        """
        named = session()
        metadata = self.metadata(self.read_backoff)
        fields = [field.get("name") for field in metadata.get("fields") or [] if isinstance(field, dict) and field.get("name")]
        if metadata.get("error") or not fields:
            # ArcGIS answers many errors with HTTP 200 and an `error` object (page_refusal()), and a layer
            # document without its field list names nothing to leave out: asking "*" then would send every
            # person field this layer has (review finding EXD-2). Refused, so the last committed table stands.
            said = metadata.get("error") or "no `fields` key"
            raise RuntimeError(f"{self.key}: the layer's metadata answered no field list ({said}), so nothing could be left out")
        dropped = self.dropped_fields(metadata)
        kept = [name for name in fields if name.lower() not in dropped]
        listed = {name.lower() for name in fields}
        rule = self.person_rule
        report_shaped(self.key, dropped, fields)
        # Person fields are left out of the field list asked for, so they never
        # cross the wire; "*" only when the layer has none to leave out.
        out_fields = "*" if len(kept) == len(fields) else ",".join(kept)
        # A server that refuses resultOffset says so in its metadata, and is read by
        # object id in batches no larger than its own maxRecordCount (lib/arcgis.py).
        paginate = (metadata.get("advancedQueryCapabilities") or {}).get("supportsPagination") is not False
        oid_field = object_id_field(metadata)
        with tempfile.TemporaryFile("w+", encoding="utf-8") as spool:
            for attempt in (1, 2):
                spool.seek(0)
                spool.truncate()
                read, count, moved = self._read_into(spool, named, out_fields, paginate, metadata, oid_field)
                if moved is None:
                    break
                if attempt == 2:
                    raise RuntimeError(f"{self.key}: the layer changed while it was read, twice ({moved}); not landed short")
                print(f"::warning title={self.key} changed while it was read::{moved}; reading the layer again, once")
            if count is not None:
                if read < count:
                    raise RuntimeError(f"{self.key}: the server counts {count} features and {read} were read")
                proofs[self.table] = count
            if self.cadence == "monthly":
                peak = getrusage(RUSAGE_SELF).ru_maxrss // 1024  # KiB on Linux
                print(f"  {self.key}: {read} features, {spool.tell():,} bytes spooled, peak RSS {peak:,} MB")
            spool.seek(0)
            for line in spool:
                feature = json.loads(line)
                row = {
                    name: value
                    for name, value in (feature.get("properties") or {}).items()
                    if not left_out_of_row(name, listed, dropped, rule)
                }
                row["geometry"] = feature.get("geometry")
                yield row

    def _read_into(self, spool, named, out_fields: str, paginate: bool, metadata: dict, oid_field: str):
        """One whole read into `spool`: (features read, the server's count after, why the read cannot stand or None).

        AN OFFSET PAGE IS ASKED OF THE LAYER AS IT IS AT THAT MOMENT, so a row
        that leaves the `where` set below the offset between two pages shifts
        every later row down one and the next page starts a row late, and one
        that joins it below the offset shifts them up and repeats a row. Either
        way a live row is never served while the rows read can still equal
        the count read after them (review finding EXD-1: a site reopening
        under `status = 'closed'` cost a still-closed site its row, and the
        count passed). So the count is read before the pages as well as
        after: a read of more than one page whose count moved between the two
        may have been shifted, and a read that makes up the count only with
        repeated object ids served one row in place of another. Either is read
        again by the caller, once, and refused if the second read is no better.
        One page cannot be shifted, so its count moving is no reason to read
        again; a read shorter than the count is the caller's refusal, as
        before; and a layer read by object id (`paginate` false) asks for ids,
        not offsets, so it cannot be shifted at all.

        STILL OPEN: a row leaving the set and another joining it inside one
        read leaves the count where it was and repeats nothing, and that skip
        is not seen. Keyset paging (`orderByFields` on the object id, `where`
        past the last id read) would close it, and changes every page query
        every layer is asked; it is not built (Reasoned, not measured: no
        registered server has been tried with it).
        """
        query_url = self.url + "/query"
        before = layer_count(query_url, where=self.where, session=named, backoff=self.read_backoff) if paginate else None
        pages = iter_layer_pages(
            self.url,
            where=self.where,
            out_fields=out_fields,
            session=named,
            backoff=self.read_backoff,
            return_z=self.return_z,
            paginate=paginate,
            page_size=None if paginate else min(ARCGIS_PAGE_SIZE, metadata.get("maxRecordCount") or ARCGIS_PAGE_SIZE),
        )
        read, pages_read, ids = 0, 0, set()
        for page in pages:
            pages_read += 1
            for feature in page:
                spool.write(json.dumps(feature, separators=(",", ":")))
                spool.write("\n")
                read += 1
                if ids is not None:
                    oid = feature_object_id(feature, oid_field)
                    if oid is None:
                        ids = None  # a feature with no id: the repeat check cannot be made, and is not guessed
                    else:
                        ids.add(oid)
        count = layer_count(query_url, where=self.where, session=named, backoff=self.read_backoff)
        if not paginate or count is None:
            return read, count, None
        if ids is not None and len(ids) < count <= read:
            return read, count, f"{len(ids)} distinct object ids in {read} features read, and the server counts {count}"
        if pages_read > 1 and before is not None and before != count:
            return read, count, f"the server counted {before} features before the {pages_read} pages and {count} after"
        return read, count, None


def arcgis_layer(key: str, **overrides) -> ArcgisLayer:
    registry_entry(key)  # a key that is not registered fails at import, in the layout test, not mid-run
    return ArcgisLayer(key=key, **overrides)


@dataclass(frozen=True)
class SocrataDataset(PersonRuled, Resource):
    """A Socrata dataset read as GeoJSON through lib/socrata.py's own loop, under the entry's `where`.

    The `where` is a SoQL predicate the portal applies, and it is the one
    filter that runs before dbt here: NYC DOT's bike network is about 29,700
    rows, of which the entry's predicate keeps the off-street greenways
    (lib/socrata.py). Pages come from `fetch_dataset_geojson`, ordered on
    `:id` so an offset is safe, and the read is held to the portal's own
    `count(*)` under the same `where` afterwards, the Socrata half of ELT.md's
    "an allowed zero counts only with the upstream's own count". Every
    request passes the host's gate (host_gated): NYC's portal asks
    `Crawl-delay: 1`, and nycparks and nycdot read it from two threads.
    """

    @property
    def entry(self) -> dict:
        return registry_entry(self.key)

    @property
    def where(self) -> str | None:
        return self.entry.get("where") or None

    def _soql(self, select: str) -> dict:
        params = {"$select": select}
        if self.where:
            params["$where"] = self.where
        url = dataset_url(self.entry["domain"], self.entry["dataset_id"], extension="json")
        rows = request_with_retry(url, session=host_gated(self.entry), params=params, timeout=60).json()
        return rows[0] if rows else {}

    def count(self) -> int | None:
        value = self._soql("count(*) as n").get("n")
        return int(value) if value is not None else None

    @property
    def zero_proof(self) -> str:
        return "the portal's count(*) under the entry's own where (count())"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """`count(*)` and `max(:updated_at)` under the entry's own `where`, with the `where` text kept.

        Measured 2026-10-01 (ELT.md, "The skip-unchanged check, by platform"):
        SODA ignores `If-None-Match`, `viewLastModified` is wrong in both
        directions, and `rowsUpdatedAt` is dataset-wide, so `nyc_park_drives`'
        filtered rows max at 2026-08-16 while the dataset reads 2026-09-26. A
        delete lowers the count (Reasoned). The `where` is in the marker because
        tightening a filter changes the rows while every date stays put.
        """
        try:
            answer = self._soql("count(*) as n, max(:updated_at) as updated")
        except (requests.RequestException, ValueError, KeyError, IndexError) as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if answer.get("n") is None or answer.get("updated") is None:
            return Freshness.UNKNOWN, None
        marker = {"n": str(answer["n"]), "max_updated_at": str(answer["updated"]), "where": self.where or ""}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        """Every row under the `where`, as properties plus `geometry` and Socrata's `:id` as `_socrata_id`.

        Read whole before the first row is yielded, as ArcgisLayer does, so a
        short read raises before dlt normalizes anything.
        """
        collection = fetch_dataset_geojson(
            self.entry["domain"], self.entry["dataset_id"], where=self.where, session=host_gated(self.entry)
        )
        features = collection["features"]
        count = self.count()
        if count is not None:
            if len(features) < count:
                raise RuntimeError(f"{self.key}: the portal counts {count} rows and {len(features)} were read")
            proofs[self.table] = count
        kept = self.without_people([feature.get("properties") or {} for feature in features])
        for feature, row in zip(features, kept, strict=True):
            row["_socrata_id"] = feature.get("id")
            row["geometry"] = feature.get("geometry")
            yield row


def socrata_dataset(key: str, **overrides) -> SocrataDataset:
    entry = registry_entry(key)
    if not entry.get("domain") or not entry.get("dataset_id"):
        raise KeyError(f"{key} has no domain and dataset_id in sources.json")
    return SocrataDataset(key=key, **overrides)


# WordPress lists cap `per_page` at 100 and page the rest; a short page is the
# last one. MAX_PAGES is a ceiling, so a misbehaving site cannot spin a run
# forever, and reaching it raises rather than loading a truncated list.
WP_PAGE_SIZE = 100
WP_MAX_PAGES = 20
# Taxonomy terms are refreshed once a day, riding the hourly lane when due:
# a renamed term does not touch a post's `modified` (ELT.md, "Every node
# carries its cadence"; Reasoned).
TERMS_CADENCE_REASON = "a renamed term does not touch a post's modified, so terms are read daily (ELT.md)"


def _wp_api(entry: dict) -> str:
    """The site's REST root, at the origin of the page the registry row names for a person."""
    parsed = urlparse(entry["url"])
    return f"{parsed.scheme}://{parsed.netloc}/wp-json/wp/v2"


def wp_list(api: str, route: str, params: dict, http: requests.Session) -> tuple[list, int | None]:
    """Every page of a WordPress list route, and the site's own `X-WP-Total` for it.

    Stops at `X-WP-TotalPages` as well as on a short page: a list of exactly
    100 fills page 1, and the posts route answers a page past the last with
    HTTP 400 `rest_post_invalid_page_number` (measured on NYNJTC 2026-10-01;
    its taxonomy routes answer 200 and an empty list instead).
    """
    collected, total = [], None
    for page in range(1, WP_MAX_PAGES + 1):
        response = request_with_retry(
            f"{api}/{route}", session=http, params={"per_page": WP_PAGE_SIZE, "page": page, **params}, timeout=60
        )
        if total is None and response.headers.get("X-WP-Total") is not None:
            total = int(response.headers["X-WP-Total"])
        batch = response.json()
        if not isinstance(batch, list):
            raise ValueError(f"{route} answered {type(batch).__name__}, not a list: the site's API has changed shape")
        collected.extend(batch)
        last_page = response.headers.get("X-WP-TotalPages")
        if len(batch) < WP_PAGE_SIZE or (last_page is not None and page >= int(last_page)):
            return collected, total
    raise RuntimeError(f"{route}: still paging at {WP_MAX_PAGES} pages, which is a ceiling rather than an ending")


@dataclass(frozen=True)
class WordpressPosts(PersonRuled, Resource):
    """One WordPress category's posts, or one custom post type's, a row each, from the site's REST API.

    The registry row's `url` is the category page a person reads
    (`/category/<slug>/`); the REST root is that page's origin plus
    `/wp-json/wp/v2`, and the category's id is looked up by its slug each run,
    so a renumbered category is a refused run rather than an empty one. Posts
    land as WordPress serves them, `title` and `content` still rendered, with
    their taxonomy ids: the terms are their own daily table
    (`wordpress_terms`), resolved in dbt (ELT.md, "Source kinds").

    THREE OPTIONS, each for a site decision 53's inventory measured on
    2026-10-03 (extract/_notices.py's module docstring says what that read
    was, and the bracketed batch which of its workers read it):

    - `category_slugs`: several categories as one table. The Florida Trail
      Association files its closures and notices to hikers under five
      (ids 37, 40, 41, 42 and 43; X-WP-Total 14 under all five) [b3]. The
      slugs go to WordPress as one comma-separated `slug`, which it reads as
      a list (Reasoned from its REST API's list parameters; a site that did
      not would resolve a slug to no id and refuse the run, never narrow it).
      Left empty, the url's own slug is the one category.
    - `post_type`: a custom post type's `rest_base`, read whole: the Green
      Mountain Club's alerts are the `alert` route (X-WP-Total 15, with its
      own `alert-category` taxonomy) [b5]. Such posts sit in no category, so
      this takes none, and the url is then the page a person reads.
    - `crawl_delay`: the host's robots.txt Crawl-delay, kept between every
      request this resource sends (extract/_notices.py's polite()):
      aztrail.org, greenmountainclub.org and carolinamountainclub.org ask 10
      [b1, b3, b5]. NYNJTC asks none (its robots.txt answered 200 and empty,
      2026-10-01), and 0 sends as this always has.

    Every request carries a query string, so a host whose robots.txt
    disallows them (extract/_notices.py's QUERY_DISALLOWED_HOSTS:
    foothillstrail.org and newenglandtrail.org) is refused at import.

    PEOPLE. A post is asked for whole and its fields judged by PersonRule:
    PERSON_FIELDS, WP_DROPPED and the row's `person_fields` out, then any
    name PERSON_SHAPED reads as a person's, so a theme's `author_info` or a
    plugin's `contact_email` that a site adds after its row was read never
    lands (review finding SEC-2 of PR #1805). A `_fields` allowlist on the
    request was the other fix, and is not used because it would drop
    columns models read: every suggested-hike staging model carries all of
    a post's columns but its prose in `properties` (GMC's six hike
    taxonomies among them), the notices' wording union reads every text
    column of the base model, and each site's own taxonomy and plugin
    fields would need listing per row. What the name rule cannot see is a
    person under a name it does not know, nested or not; such a field is
    the row's `person_fields`, as `content` is where a post carries a
    telephone number.
    """

    category_slugs: tuple[str, ...] = ()
    post_type: str | None = None
    crawl_delay: float = 0.0

    @property
    def entry(self) -> dict:
        return registry_entry(self.key)

    @property
    def api(self) -> str:
        return _wp_api(self.entry)

    @property
    def route(self) -> str:
        return self.post_type or "posts"

    @property
    def zero_proof(self) -> str:
        """The site's `X-WP-Total`, which wp_list() reads off the same answers as the posts; none without that header."""
        return "the site's X-WP-Total for the category, post type or parent read (wp_list())"

    @property
    def category_slug(self) -> str:
        parts = [part for part in urlparse(self.entry["url"]).path.split("/") if part]
        if len(parts) < 2 or parts[-2] != "category":
            raise KeyError(f"{self.key}: url is not a /category/<slug>/ page: {self.entry['url']}")
        return parts[-1]

    @property
    def scope_slugs(self) -> tuple[str, ...]:
        """The categories the posts are read from: none for a custom post type, else the named ones or the url's."""
        if self.post_type:
            return ()
        return self.category_slugs or (self.category_slug,)

    def _session(self) -> requests.Session:
        return polite(session(), self.crawl_delay) if self.crawl_delay else session()

    def category_ids(self, http: requests.Session) -> list[int]:
        slugs = self.scope_slugs
        found, _ = wp_list(self.api, "categories", {"slug": ",".join(slugs), "_fields": "id,slug"}, http)
        ids = []
        for slug in slugs:
            matched = [term["id"] for term in found if term.get("slug") == slug]
            if len(matched) != 1:
                raise RuntimeError(f"{self.key}: category {slug!r} resolves to {len(matched)} ids")
            ids.append(matched[0])
        return ids

    def scope(self, http: requests.Session) -> dict:
        """The list route's own filter: the category ids, or none for a custom post type."""
        if self.post_type:
            return {}
        return {"categories": ",".join(str(term) for term in self.category_ids(http))}

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """A hash of the category's (id, modified) set, and its `X-WP-Total`.

        One small request: `_fields=id,modified_gmt,slug`. An unpublished post
        leaves the set, so a lifted closure moves the marker. The site's feed
        ETag and `Last-Modified` are site-wide (GATC's alerts and events feeds
        returned the same validator, measured 2026-10-01), so no feed validator
        ever decides FRESH here.
        """
        try:
            http = self._session()
            posts, total = wp_list(self.api, self.route, {**self.scope(http), "_fields": "id,modified_gmt,slug"}, http)
        except (requests.RequestException, ValueError, KeyError, RuntimeError) as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if total is None:
            return Freshness.UNKNOWN, None
        pairs = sorted((post.get("id"), post.get("modified_gmt")) for post in posts)
        marker = {"total": str(total), "set_sha256": hashlib.sha256(json.dumps(pairs).encode()).hexdigest()}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    @property
    def plumbing(self) -> frozenset[str]:
        """WP_DROPPED, which PersonRule leaves out of every post with the row's own `person_fields`.

        Decision 59 leaves a free-text field that carries personal data out
        whole, never redacted. Measured in decision 53's phase B (2026-10-03):
        the Ozark Highlands Trail's alert posts carry a maintenance e-mail
        address and a telephone number in `content`, TEHCC's Appalachian
        Trail posts 14 telephone numbers and Trailkeepers of Oregon's
        condition posts 3, so those rows list `content` and `excerpt` in
        their `person_fields`.
        """
        return WP_DROPPED

    def rows(self, proofs: dict[str, int]):
        http = self._session()
        posts, total = wp_list(self.api, self.route, self.scope(http), http)
        if total is not None:
            if len(posts) < total:
                raise RuntimeError(f"{self.key}: the site counts {total} posts and {len(posts)} were read")
            proofs[self.table] = total
        yield from self.without_people(posts)


# Fields a post carries that are WordPress plumbing or name a person. `author`
# is a user id that resolves to a person, and Yoast's SEO blocks
# (`yoast_head`, `yoast_head_json`) spell that person's name out ("Written
# by"); `_links` is the API's own hypermedia. Read off NYNJTC's 18 posts,
# 2026-10-01. The Green Mountain Club's `alert` posts add Spectra's
# `uagb_author_info`, whose `display_name` is a staff member's, and
# `spectra_custom_meta`, which carries edit locks and Yoast's meta (decision
# 53's inventory [b5], 2026-10-03). All in One SEO's `aioseo_head` and
# `aioseo_head_json` are Yoast's two blocks under another plugin's name, and
# spell the author out the same way: added for review finding SEC-2 of PR
# #1805 on the review's word, as no registered site was read serving them.
WP_DROPPED = frozenset(
    {
        "author",
        "_links",
        "guid",
        "ping_status",
        "comment_status",
        "template",
        "meta",
        "yoast_head",
        "yoast_head_json",
        "aioseo_head",
        "aioseo_head_json",
        "class_list",
        "uagb_author_info",
        "spectra_custom_meta",
    }
)


@dataclass(frozen=True)
class WordpressTerms(Resource):
    """The site's place taxonomies' terms, a row each with its taxonomy: the lookup a post's ids resolve against.

    Its own table, `<posts table>_terms`, and its own daily cadence (a
    renamed term moves no post). The taxonomies are the registry row's
    `taxonomies`, or lib/nynjtc_alerts.py's PLACE_TAXONOMIES, which NYNJTC's
    fetcher reads today.
    """

    taxonomies: tuple[str, ...] = ()

    @property
    def table(self) -> str:
        return super().table + "_terms"

    @property
    def part(self) -> str:
        return "terms"

    @property
    def api(self) -> str:
        return _wp_api(registry_entry(self.key))

    @property
    def zero_proof(self) -> str:
        """The site's own counts; an empty taxonomy raises first (rows()), so this never lands a zero."""
        return "the sum of each taxonomy's X-WP-Total; an empty taxonomy raises before any zero"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """Always read when due: four small lists, once a day, cost less than a marker that could lie."""
        return Freshness.UNKNOWN, None

    def rows(self, proofs: dict[str, int]):
        http = session()
        rows, totals = [], []
        for taxonomy in self.taxonomies:
            terms, total = wp_list(self.api, taxonomy, {"_fields": "id,name,slug,count"}, http)
            if not terms:
                # An empty vocabulary is a route that stopped answering in the shape
                # expected, not a site that tags nothing (fetch_nynjtc_alerts.py's rule).
                raise RuntimeError(f"{self.key}: the {taxonomy!r} taxonomy came back empty, which is a broken read")
            if total is not None and len(terms) < total:
                raise RuntimeError(f"{self.key}: {taxonomy} counts {total} terms and {len(terms)} were read")
            totals.append(total)
            rows.extend({**term, "taxonomy": taxonomy} for term in terms)
        if all(total is not None for total in totals):
            proofs[self.table] = sum(totals)
        yield from rows


def wordpress_posts(key: str, **overrides) -> WordpressPosts:
    if "category_slugs" in overrides:
        overrides["category_slugs"] = tuple(overrides["category_slugs"])
    resource = WordpressPosts(key=key, **overrides)
    if refused := query_refused(resource.entry["url"]):
        raise ValueError(f"{key}: {refused}, and every WordPress list request carries one")
    if resource.post_type and resource.category_slugs:
        raise ValueError(f"{key}: a custom post type sits in no category, so post_type takes no category_slugs")
    resource.scope_slugs  # a url that is not a category page fails at import, in the layout test
    return resource


def wordpress_terms(key: str, taxonomies: tuple[str, ...], **overrides) -> WordpressTerms:
    if refused := query_refused(registry_entry(key)["url"]):
        raise ValueError(f"{key}: {refused}, and every WordPress list request carries one")
    if not taxonomies:
        raise ValueError(f"{key}: wordpress_terms needs the taxonomies a post is tagged from")
    overrides.setdefault("cadence_override", "daily")
    overrides.setdefault("cadence_reason", TERMS_CADENCE_REASON)
    return WordpressTerms(key=key, taxonomies=tuple(taxonomies), **overrides)


# fetch_nynjtc_long_path_guide.py's throttle, one request every half second.
# nynjtc.org's robots.txt answered 200 and empty on 2026-10-01, so it asks
# for no crawl delay.
GUIDE_THROTTLE_SECONDS = 0.5

# The parsers a guide's pages are read with, by registry key. A guide is HTML
# written for people, so each one needs its own reading; a key with none here
# cannot be built.
GUIDE_PARSERS = {"nynjtc_long_path_guide": (parse_guide_index, parse_guide_section)}


@dataclass(frozen=True)
class GuidePages(Resource):
    """A guide an organization publishes as web pages: one row per section, as the guide's parser reads it.

    The registry row's `url` is the guide's index; each section page it links
    is read and parsed (ELT.md, "Source kinds": an HTML parse is extraction,
    rule SH01). A page the parser does not recognise raises, so a run never
    lands the sections that still happened to parse. Each row keeps the
    page's own sha256 beside the parse; the page's bytes go to the as-sent
    copy, which is not built yet.
    """

    @property
    def parsers(self):
        return GUIDE_PARSERS[self.key]

    @property
    def zero_proof(self) -> None:
        """None: the count is the section pages this guide's parser finds linked from its index, and an index that
        links none raises first."""
        return None

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """UNKNOWN: there is no cheap marker, so the monthly lane reads the guide whole.

        NYNJTC serves neither validator on these pages (read 2026-09-08), and
        every body differs on every render, by a WordPress gallery's random
        `galleryId` (fetch_nynjtc_long_path_guide.py). What moves is the
        parse, and seeing it means reading every page.
        """
        return Freshness.UNKNOWN, None

    def rows(self, proofs: dict[str, int]):
        parse_index, parse_section = self.parsers
        http = session()
        index = request_with_retry(registry_entry(self.key)["url"], session=http, timeout=60).text
        pages = parse_index(index)
        if not pages:
            raise RuntimeError(f"{self.key}: the index links no section page, which is a broken read")
        sections = []
        for number, url in pages:
            time.sleep(GUIDE_THROTTLE_SECONDS)
            html = request_with_retry(url, session=http, timeout=60, retryable_statuses=(429, 500, 502, 503, 504)).text
            section = parse_section(html, url, expected_number=number)
            sections.append({**section.to_dict(), "page_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest()})
        proofs[self.table] = len(pages)
        yield from sections


def guide_pages(key: str, **overrides) -> GuidePages:
    registry_entry(key)
    if key not in GUIDE_PARSERS:
        raise KeyError(f"{key}: no guide parser is registered in extract/_kinds.py's GUIDE_PARSERS")
    return GuidePages(key=key, **overrides)


# The Hike Finder's host asks for this: robots.txt `Crawl-delay: 10`, read
# 2026-10-01. fetch_hikefinder.py sends two a second; this layer does as the
# host asks, so its 385 pages and 113 tracks take about 83 minutes on the
# monthly lane (ELT.md, "The skip-unchanged check, by platform"). It is kept
# by extract/_notices.py's per-host gate, end to start, on every request the
# sign-in's POST included: the POST used to keep only fetch_hikefinder.py's
# own 0.5 s, so the listing followed it inside the delay (review finding EXD-4).
HIKEFINDER_THROTTLE_SECONDS = 10


@dataclass(frozen=True)
class PublishedHikes(Resource):
    """NYNJTC's hike write-ups through the Hike Finder export, one row per hike as lib/hikefinder.py parses it.

    The listing names every hike and states its own total, which is the
    proof the run check holds the rows to; a listing whose links and stated
    total disagree raises, as fetch_hikefinder.py refuses it. A hike with a
    published track carries the GPX as served in `gpx`, never as parsed
    points, because the track is somebody's survey and a later parse may want
    what this one did not keep. The export is behind a site password, read
    from HIKEFINDER_PASSWORD (Extract's credential table in ELT.md); with no
    password the listing is a login form, links no hike, and the run raises
    rather than landing an empty table.
    """

    @property
    def zero_proof(self) -> str:
        """The total the listing states for itself; a listing that links no hike raises first, so this never lands a zero."""
        return "the Hike Finder listing's own stated total; a listing that links no hike raises before any zero"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """UNKNOWN: `hikes.php` serves neither an ETag nor a Last-Modified and there is no feed (measured 2026-09-15)."""
        return Freshness.UNKNOWN, None

    def _get(self, http: requests.Session, url: str) -> str:
        return request_with_retry(url, session=http, timeout=60).text

    def rows(self, proofs: dict[str, int]):
        base = registry_entry(self.key)["url"].rstrip("/") + "/"
        http = polite(session(), HIKEFINDER_THROTTLE_SECONDS)  # the host's gate, on the sign-in's POST too
        signed_in = hikefinder_sign_in(http, base)
        listing = self._get(http, urljoin(base, HIKEFINDER_LISTING_PATH))
        ids = hikefinder_listing_ids(listing)
        if not ids:
            hint = "the password was refused or the form changed" if signed_in else "no HIKEFINDER_PASSWORD was set"
            raise RuntimeError(f"{self.key}: the listing links no hike ({hint})")
        stated = hikefinder_listing_count(listing)
        if stated is not None and stated != len(ids):
            raise RuntimeError(f"{self.key}: the listing says {stated} hikes and links {len(ids)}")
        if stated is not None:
            proofs[self.table] = stated
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        for hike_id in ids:
            url = urljoin(base, HIKEFINDER_DETAIL_PATH.format(id=hike_id))
            hike = parse_hike(self._get(http, url), hike_id, url)
            if hike is None:
                raise RuntimeError(f"{self.key}: hike {hike_id} did not parse, which is the export changing shape")
            row = as_hike_row(hike, stamp)
            row["gpx"] = None
            if hike.has_published_route:
                track = self._get(http, urljoin(base, HIKEFINDER_GPX_PATH.format(id=hike_id)))
                row["gpx"] = track if parse_gpx(track) is not None else None
            yield row


def published_hikes(key: str, **overrides) -> PublishedHikes:
    registry_entry(key)
    return PublishedHikes(key=key, **overrides)


@dataclass(frozen=True)
class ClubPdf(Resource):
    """A PDF a club publishes: one row per row its parser reads, each carrying the document's own manifest.

    The registry row's `url` is the PDF. lib/club_pdfs.py's parser for the key
    turns the text layer into rows, and raises on a layout it has not seen, so
    a changed document refuses the run rather than relabelling a column. The
    manifest (url, ETag, Last-Modified, sha256, bytes) rides every row as
    `_document`, so the date the club put on the file is in the warehouse.
    The PDF's own bytes go to the as-sent copy, which is not built yet. The
    text comes from fetch_club_pdfs.py's `extract_page_texts`, which needs
    pypdf: requirements-extract.in pins it, and requirements.in's note says
    why the build jobs do not.

    THE DOCUMENT'S OWN TITLE AND CREATION DATE ride `_document` too
    (club_pdf_document_info), because the HTTP date is not the data's date.
    GATC's file, read 2026-10-04: `Last-Modified` Mon, 02 Mar 2026, and its
    embedded title "GATC Water Update July 2020.xlsx" (WATER_SOURCES.md §4),
    so a card that printed only the first would present six-year-old water
    data as this year's. Decision 75 publishes that list at low confidence
    with its document date; the title is the half of that date a hiker
    needs. Either is null where the PDF does not state it.
    """

    def _get(self, headers: dict | None = None) -> requests.Response:
        """One GET of the PDF through the host's gate (host_gated), at the row's `crawl_delay`: GATC's host asks 10 s.

        A PDF that now redirects to another host raises the session's
        RedirectRefused (extract/_notices.py's refuse_other_hosts), so the change check is UNKNOWN and the read refuses.
        """
        entry = registry_entry(self.key)
        return request_with_retry(entry["url"], session=host_gated(entry), headers=headers or None, timeout=120)

    @property
    def zero_proof(self) -> None:
        """None: rows() records no count at all, and the rows are what lib/club_pdfs.py's parser reads out of a PDF."""
        return None

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """A conditional GET, then the body's sha256: WordPress re-serves the same bytes without a 304.

        GATC's file answers with its validators (fetch_club_pdfs.py), so a 304
        is FRESH; a 200 with the same sha256 as the last load is FRESH too.

        A marker recorded under an older CLUB_PDF_MANIFEST is STALE whatever
        the bytes, and is asked for without validators so no 304 can keep it:
        the rows it loaded lack what `_document` carries now, and unchanged
        bytes would otherwise keep them for good. GATC's card would then say
        "a PDF of 2026-03-02" and never "July 2020".
        """
        current = bool(recorded) and recorded.get("manifest") == CLUB_PDF_MANIFEST
        headers = {}
        if current:
            if recorded.get("etag"):
                headers["If-None-Match"] = recorded["etag"]
            if recorded.get("last_modified"):
                headers["If-Modified-Since"] = recorded["last_modified"]
        try:
            response = self._get(headers)
        except (requests.RequestException, RuntimeError) as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if response.status_code == 304:
            return Freshness.FRESH, recorded
        marker = {
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "manifest": CLUB_PDF_MANIFEST,
        }
        if not current or not recorded.get("sha256"):
            return Freshness.STALE, marker
        return (Freshness.FRESH if recorded["sha256"] == marker["sha256"] else Freshness.STALE), marker

    def rows(self, proofs: dict[str, int]):
        response = self._get()
        response.raise_for_status()
        body = response.content
        rows = CLUB_PDF_PARSERS[self.key](extract_page_texts(body))
        document = {
            "url": registry_entry(self.key)["url"],
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
            **club_pdf_document_info(body),
        }
        for row in rows:
            yield {**row, "_document": document}


#: What a ClubPdf row's `_document` carries, by version: 1 the HTTP manifest, 2 the PDF's own title and creation
#: date beside it (2026-10-05). A load recorded under an older version is read again (ClubPdf.change_check).
CLUB_PDF_MANIFEST = 2


def club_pdf_document_info(body: bytes) -> dict:
    """The PDF's own `/Title` and creation date (ISO 8601), each None where the file states none.

    Read with pypdf, as the text is (extract_page_texts). A metadata block
    pypdf cannot read is None for both rather than a failed load: the rows
    were already read from the same bytes, and a missing title only means
    the card says less about the document's age, never something wrong.
    """
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        metadata = PdfReader(io.BytesIO(body)).metadata
    except (PdfReadError, ValueError):
        metadata = None
    if metadata is None:
        return {"title": None, "created": None}
    title = (metadata.title or "").strip() or None
    try:
        created = metadata.creation_date
    except ValueError:
        created = None
    return {"title": title, "created": created.isoformat() if created else None}


def club_pdf(key: str, **overrides) -> ClubPdf:
    registry_entry(key)
    if key not in CLUB_PDF_PARSERS:
        raise KeyError(f"{key}: lib/club_pdfs.py has no parser for it, so there is nothing to load but bytes")
    return ClubPdf(key=key, **overrides)


@dataclass(frozen=True)
class OpentrailFeed(PersonRuled, Resource):
    """opentrail.org's A.T. waypoints, one row per feature, with every user comment left out.

    The API URL is fetch_opentrail.py's `API_URL`, its one home: opentrail is
    a non-registry input (ELT.md, "What moves"), so it has no sources.json row
    to read one from. Comments are dropped inside the resource, before dlt
    sees a row, because they are named individuals' own contributions and not
    ours to redistribute (fetch_opentrail.py's `strip_comments`). The
    API documents ETag and If-None-Match, so the change check is a
    conditional GET and a 304 is FRESH. The key is `at`, so the table keeps
    the name dbt already reads, `raw_opentrail__at`.
    """

    def _get(self, etag: str | None = None) -> requests.Response:
        headers = {"If-None-Match": etag} if etag else None
        return request_with_retry(OPENTRAIL_API_URL, session=session(), params={"trail": "AT"}, headers=headers, timeout=60)

    @property
    def zero_proof(self) -> None:
        """None: rows() records no count, so its table is held to the shrink floor and may never be empty."""
        return None

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        try:
            response = self._get((recorded or {}).get("etag"))
        except requests.RequestException as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if response.status_code == 304:
            return Freshness.FRESH, recorded
        etag = response.headers.get("ETag")
        if not etag:
            return Freshness.UNKNOWN, None
        return (Freshness.STALE if recorded is None else compare_marker(recorded.get("etag"), etag)), {"etag": etag}

    def column_hints(self) -> dict:
        # feature_id hinted so the column exists when no feature carries an id,
        # as on CI's fixtures (extract/_fixtures.py); dlt creates no column it
        # never saw a value for.
        return {"geometry": {"data_type": "json"}, "feature_id": {"data_type": "text"}}

    def rows(self, proofs: dict[str, int]):
        response = self._get()
        response.raise_for_status()
        features = strip_opentrail_comments(response.json())["features"]
        kept = self.without_people([feature.get("properties") or {} for feature in features])
        for feature, row in zip(features, kept, strict=True):
            row["feature_id"] = feature.get("id")
            row["geometry"] = feature.get("geometry")
            yield row


def opentrail_feed(**overrides) -> OpentrailFeed:
    return OpentrailFeed(key="at", **overrides)


@dataclass(frozen=True)
class HydrographyWatch(Resource):
    """The usgs_3dhp watch: which 3DHP work units the corridor's flowlines come from, one row per probe box.

    A watch, not a fetch (lib/source_registry.py's WATCHED_ONLY): no 3DHP
    geometry lands, only the answer that says whether USGS has resurveyed the
    corridor. The boxes are check_freshness.py's CORRIDOR_PROBES, five
    0.04-degree envelopes on the footpath, and the query is the registry row's
    `freshness.url`. Every box must name a work unit, or the read raises, so a
    resurveyed stretch cannot hide behind four boxes that still say `NHD`
    (check_freshness.py's `upstream_hydrography_marker`, whose rule this
    keeps). Measured 2026-08-14: all five answer `NHD`.
    """

    @property
    def zero_proof(self) -> None:
        """None: the count is CORRIDOR_PROBES' length, this code's own constant, and a probe naming no unit raises."""
        return None

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """UNKNOWN: five one-row queries a month cost less than a marker that could lie."""
        return Freshness.UNKNOWN, None

    def rows(self, proofs: dict[str, int]):
        url = registry_entry(self.key)["freshness"]["url"]
        http = session()
        rows = []
        for index, (west, south, east, north) in enumerate(CORRIDOR_PROBES):
            answer = request_with_retry(
                url,
                session=http,
                params={
                    "f": "json",
                    "where": "1=1",
                    "outFields": "workunitid",
                    "returnGeometry": "false",
                    "returnDistinctValues": "true",
                    "geometry": f"{west},{south},{east},{north}",
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": 4326,
                    "spatialRel": "esriSpatialRelIntersects",
                },
                timeout=30,
            ).json()
            units = sorted(
                {str(unit) for feature in answer["features"] if (unit := (feature.get("attributes") or {}).get("workunitid"))}
            )
            if not units:
                raise RuntimeError(f"{self.key}: probe {index} named no work unit, which is not an answer about that stretch")
            rows.append({"probe": index, "west": west, "south": south, "east": east, "north": north, "workunitids": units})
        proofs[self.table] = len(CORRIDOR_PROBES)
        yield from rows


def hydrography_watch(key: str, **overrides) -> HydrographyWatch:
    entry = registry_entry(key)
    if not (entry.get("freshness") or {}).get("url"):
        raise KeyError(f"{key} has no freshness.url to ask 3DHP at")
    return HydrographyWatch(key=key, **overrides)


S3_NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
S3_MAX_PAGES = 50

# The bucket listings the extract reads, by key: each one the URL template a
# fetcher downloads from, so the listing covers exactly what that fetcher
# reads and the prefix has one home. None of these is a sources.json row
# (ELT.md, "What moves"); both are USGS's public `prd-tnm` bucket.
BUCKET_LISTINGS = {
    "tnm_3dep_13_current": DEM_TILE_URL_TEMPLATE,
    "nhd_hu4_gpkg": NHD_GPKG_URL,
}


def _bucket_and_prefix(template: str) -> tuple[str, str]:
    """`https://host/a/b/c_{x}.zip` -> ("https://host", "a/b/c_"): everything before the first placeholder."""
    parsed = urlparse(template)
    return f"{parsed.scheme}://{parsed.netloc}", parsed.path.lstrip("/").split("{", 1)[0]


@dataclass(frozen=True)
class BucketListing(Resource):
    """A public S3 bucket's objects under one prefix, one row per object: key, size, ETag, LastModified. Never the objects.

    A manifest, not a fetch. 3DEP's tiles are Cloud-Optimized GeoTIFFs read
    in place at build time, and NHD's subregions are ~270 MB zips read
    offline, so what lands is the listing that says whether either moved.
    One ListObjectsV2 walk replaces fetch_elevation.py's 476 HEADs (ELT.md,
    "The skip-unchanged check, by platform"). Measured 2026-10-01: 3DEP's
    `current/` lists 5,967 objects (1,449 of them tiles) in 6 pages, 1.8 MB
    and 1.8 s; NHD's HU4 GeoPackages 735 objects in 1 page, 195 KB and 0.8 s.
    Every object lands, the `.xml` and `.jpg` beside each file included,
    because the only filter before dbt is one the request carries.

    The change check walks the same listing and hashes every (key, ETag,
    size), so a replaced object moves the marker however its date reads.
    The walk raises unless the last page says it is the last, so a listing
    cut short is never read as the whole bucket.
    """

    def _walk(self) -> list[dict]:
        bucket, prefix = _bucket_and_prefix(BUCKET_LISTINGS[self.key])
        http, token, objects = session(), None, []
        for _ in range(S3_MAX_PAGES):
            params = {"list-type": "2", "prefix": prefix}
            if token:
                params["continuation-token"] = token
            page = ElementTree.fromstring(request_with_retry(f"{bucket}/", session=http, params=params, timeout=60).content)
            for item in page.findall("s:Contents", S3_NS):
                objects.append(
                    {
                        "key": item.findtext("s:Key", namespaces=S3_NS),
                        "size": int(item.findtext("s:Size", namespaces=S3_NS)),
                        "etag": item.findtext("s:ETag", namespaces=S3_NS),
                        "last_modified": item.findtext("s:LastModified", namespaces=S3_NS),
                        "storage_class": item.findtext("s:StorageClass", namespaces=S3_NS),
                    }
                )
            if page.findtext("s:IsTruncated", namespaces=S3_NS) != "true":
                return objects
            token = page.findtext("s:NextContinuationToken", namespaces=S3_NS)
            if not token:
                raise RuntimeError(f"{self.key}: a truncated page with no continuation token")
        raise RuntimeError(f"{self.key}: still truncated after {S3_MAX_PAGES} pages")

    def column_hints(self) -> dict:
        return {
            "key": {"data_type": "text"},
            "size": {"data_type": "bigint"},
            "etag": {"data_type": "text"},
            "last_modified": {"data_type": "text"},
            "storage_class": {"data_type": "text"},
        }

    @staticmethod
    def _marker(objects: list[dict]) -> dict:
        digest = hashlib.sha256(json.dumps(sorted((o["key"], o["etag"], o["size"]) for o in objects)).encode()).hexdigest()
        return {"objects": len(objects), "sha256": digest}

    @property
    def zero_proof(self) -> str:
        """The bucket's own listing of the prefix, whole: _walk() raises unless its last page says IsTruncated false."""
        return "the bucket's ListObjectsV2 listing under the prefix, its last page saying IsTruncated false"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        try:
            marker = self._marker(self._walk())
        except (requests.RequestException, ElementTree.ParseError, RuntimeError) as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        objects = self._walk()
        proofs[self.table] = len(objects)
        yield from objects


def bucket_listing(key: str, **overrides) -> BucketListing:
    if key not in BUCKET_LISTINGS:
        raise KeyError(f"{key}: no bucket listing by that name in extract/_kinds.py's BUCKET_LISTINGS")
    return BucketListing(key=key, **overrides)


# NWS's alert properties, as /alerts/active served them on 2026-10-01: all 30
# on each of 353 alerts, besides JSON-LD's `@id` (the feature's own `id`, on
# 353 of 353) and `@type` (`wx:Alert` on all 353), which are left out.
# Hinting every one is what makes a column exist when it is null on every
# alert of a run, or when a quiet hour lands no alert at all (ELT.md, "dlt
# configuration requirements"). The times stay text: dlt reads an ISO stamp as
# a timestamp and normalises it to UTC (measured 2026-10-01, dlt 1.30.0),
# which loses the issuing office's offset that NWS's own words carry, and the
# exporter relays these fields exactly (export_weather_alerts.py's RELAYED).
NWS_TEXT_PROPERTIES = (
    "id",
    "areaDesc",
    "sent",
    "effective",
    "onset",
    "expires",
    "ends",
    "status",
    "messageType",
    "category",
    "severity",
    "certainty",
    "urgency",
    "event",
    "sender",
    "senderName",
    "headline",
    "description",
    "instruction",
    "response",
    "note",
    "scope",
    "code",
    "language",
    "web",
)
NWS_JSON_PROPERTIES = ("geocode", "affectedZones", "references", "parameters", "eventCode")


@dataclass(frozen=True)
class NwsAlerts(PersonRuled, Resource):
    """Every active NWS alert in the US, one row per message, read in full every run.

    The endpoint is lib/nws_alerts.py's, shared with export_weather_alerts.py,
    which bakes today's `conditions/weather_alerts.json` from the same body.
    NWS is a non-registry input (ELT.md, "What moves"). Nothing is filtered
    here: `Test` messages and cancellations land and staging leaves them out
    (WN01, `stg_nws__warnings`), because a filter belongs in the extract only
    when the request carries it (the dlt skill, "Load every club, gate
    publication downstream").

    No change check: `/alerts/active` ignores both If-None-Match and
    If-Modified-Since, each answering 200 with the same ETag (measured
    2026-10-01, ELT.md, "The skip-unchanged check, by platform"), so every run
    reads it, one request a run.

    THE ZERO. A quiet hour is a real answer, so the proof is the body's own
    feature count: a 200 FeatureCollection with no features proves the zero.
    Anything else raises in check_nws_response, and a failed request raises in
    request_with_retry, so the run refuses before the load and the last good
    table stands. A failed request never becomes an empty table, which would
    read as "no warnings" (ELT.md, "Source kinds").
    """

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        return Freshness.UNKNOWN, None

    @property
    def zero_proof(self) -> str:
        """THE ZERO in the docstring above: a 200 FeatureCollection with no features (lib/nws_alerts.py's check_response)."""
        return "a 200 whose body is a FeatureCollection with no features (lib/nws_alerts.py's check_response())"

    def column_hints(self) -> dict:
        hints = {name: {"data_type": "text"} for name in (*NWS_TEXT_PROPERTIES, "feature_id", "collection_updated")}
        hints.update({name: {"data_type": "json"} for name in (*NWS_JSON_PROPERTIES, "geometry")})
        return hints

    def rows(self, proofs: dict[str, int]):
        http = session()
        http.headers["Accept"] = NWS_ACCEPT
        body = request_with_retry(NWS_ALERTS_URL, session=http, timeout=60, label="NWS active alerts").json()
        features = check_nws_response(body)
        proofs[self.table] = len(features)
        properties = [
            {name: value for name, value in (f.get("properties") or {}).items() if not name.startswith("@")} for f in features
        ]
        for feature, row in zip(features, self.without_people(properties), strict=True):
            row["feature_id"] = feature.get("id")
            row["geometry"] = feature.get("geometry")
            # The collection's own `updated`, which the bake publishes as
            # `nws_updated`. A run that lands no alert has nowhere to keep it;
            # `_extract_runs.checked_at` is when that run asked.
            row["collection_updated"] = body.get("updated")
            yield row


def nws_alerts(**overrides) -> NwsAlerts:
    return NwsAlerts(key="alerts", **overrides)


# Each of OurHike's own conditions artifacts: the table its reader must be
# able to see, and the bake's own query text, run unchanged. The text is
# export_conditions.py's, held to the served schemas in both directions by
# backend/tests/test_conditions_publisher_contract.py, so what reaches the raw
# store is what reaches a phone today.
CONDITIONS_QUERIES = {
    "closures": ("closures", export_conditions.PUBLIC_CLOSURES_SQL),
    "reports": ("reports", export_conditions.PUBLIC_REPORTS_SQL),
    "notes": ("field_notes", export_conditions.PUBLIC_NOTES_SQL),
    "disputes": ("field_notes", export_conditions.PUBLIC_DISPUTES_SQL),
}

# The person columns the four query texts leave in the database: who reported,
# who verified, who hid a note, which maintainer. A second line behind the
# query text, so that a column added under one of these names fails the read
# rather than landing (#252, #430).
WITHHELD_COLUMNS = frozenset({"reported_by", "reporter_id", "verified_by", "hidden_by", "maintainer_id"})

# Postgres type names -> dlt data types, for describing a query's own columns.
# A type not listed, such as an enum, loads as a string in psycopg, so it lands
# as text.
POSTGRES_TYPES = {
    "bool": "bool",
    "int2": "bigint",
    "int4": "bigint",
    "int8": "bigint",
    "float4": "double",
    "float8": "double",
    "numeric": "decimal",
    "date": "date",
    "timestamp": "timestamp",
    "timestamptz": "timestamp",
    "json": "json",
    "jsonb": "json",
}


@dataclass(frozen=True)
class ConditionsQuery(Resource):
    """One of OurHike's own conditions artifacts, read from its Postgres through the bake's own query.

    Decision 6: moderator-verified rows only, hourly. The query is
    export_conditions.py's PUBLIC_*_SQL, whole, so its moderation predicate,
    its 90-day and five-per-place windows, and its two-account dispute rule
    all hold here as they hold in the bake, and `verified_by` and
    `reporter_id` never leave the database. The connection is the bake's own
    CONDITIONS_DATABASE_URL, so each conditions leg reads its own environment.

    Not dlt's sql_table. Its reflected column hints are the base table's,
    not the query's (measured 2026-10-01 on Postgres 16): for closures they
    name `reported_by` and `verified_by`, the two columns the query withholds,
    and for disputes they name `field_notes`' columns and miss the computed
    `accounts`, `latest_at` and `maintainer_said`. So the hints come from
    describing the query itself.

    The check runs reader_problem() first, as the bake does, because a missing
    grant or policy reads as zero rows ("empty is indistinguishable from a
    quiet trail"). On a table export_conditions.py's PENDING_READER_SETUP
    names, the problem is Unavailable and the lane carries on without it; on
    any other table it stops the lane. The read asks again in the same
    REPEATABLE READ transaction as the rows and their proof, the query's own
    `count(*)`, so a policy dropped between check and read cannot prove a
    false zero.
    """

    @property
    def source_table(self) -> str:
        return CONDITIONS_QUERIES[self.key][0]

    @property
    def sql(self) -> str:
        return CONDITIONS_QUERIES[self.key][1]

    def _problem(self, conn) -> str | None:
        return export_conditions.reader_problem(conn, self.source_table)

    @property
    def zero_proof(self) -> str:
        return "the moderated query's own count(*), in the rows' REPEATABLE READ transaction, after reader_problem()"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """UNKNOWN when the reader can see the table: a few hundred rows an hour cost less than a marker that could lie."""
        with psycopg.connect(export_conditions.connection_url(), connect_timeout=10) as conn:
            problem = self._problem(conn)
        if problem is None:
            return Freshness.UNKNOWN, None
        pending = export_conditions.PENDING_READER_SETUP.get(self.source_table)
        if pending is None:
            raise RuntimeError(problem)
        raise Unavailable(f"{problem} {pending}")

    def column_hints(self) -> dict:
        with psycopg.connect(export_conditions.connection_url(), connect_timeout=10) as conn:
            cursor = conn.execute(f"SELECT * FROM ({self.sql}) AS public_rows LIMIT 0")
            return {
                column.name: {
                    "data_type": POSTGRES_TYPES.get(getattr(conn.adapters.types.get(column.type_code), "name", None), "text")
                }
                for column in cursor.description
            }

    def rows(self, proofs: dict[str, int]):
        with psycopg.connect(export_conditions.connection_url(), connect_timeout=10) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            problem = self._problem(conn)
            if problem is not None:
                raise RuntimeError(f"{self.key}: {problem}")
            (count,) = conn.execute(f"SELECT count(*) FROM ({self.sql}) AS public_rows").fetchone()
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(self.sql)
                withheld = WITHHELD_COLUMNS & {column.name for column in cursor.description}
                if withheld:
                    raise RuntimeError(f"{self.key}: the query now selects {sorted(withheld)}, which never leave the database")
                rows = cursor.fetchall()
        proofs[self.table] = count
        yield from rows


def conditions_query(key: str, **overrides) -> ConditionsQuery:
    if key not in CONDITIONS_QUERIES:
        raise KeyError(f"{key}: not one of export_conditions.py's artifacts {sorted(CONDITIONS_QUERIES)}")
    return ConditionsQuery(key=key, **overrides)


@dataclass(frozen=True)
class ReviewedFile(Resource):
    """A file in git that a person reviews row by row, loaded as the rows it holds.

    The change marker is the file's sha256: the file is its own upstream, so
    it is FRESH exactly when its bytes are, and its row count is its own proof.
    `rows_key` names the list a file keeps its rows under; None loads the
    whole document as one row. With `map_key` set, `rows_key` names a map of
    id -> row instead, and each row lands with its id under that column: the
    POI identity ledger keeps its 8,563 POIs that way. `_README` is the
    file's documentation and never a column. Every other top-level field (who
    reviewed it and when, the upstream marker it was reviewed against) rides
    each row as `_file`, so the "as of" a phone prints is in the warehouse and
    not only in git.
    """

    path: str = ""
    rows_key: str | None = None
    map_key: str | None = None
    # (column, dlt data type) pairs, for a file whose schema is written down
    # somewhere: dlt creates no column it never saw a value for, so a field no
    # row carries yet would otherwise be missing from the table.
    hints: tuple[tuple[str, str], ...] = ()
    # For a file a gate checks field by field (the podcast episodes): each row
    # lands whole in one `row_json` column, the JSON text the reviewer wrote,
    # and dbt reads its fields. With no `rows_key` the whole document is that
    # one row, which is how sources.json lands, its blocks beside its rows.
    # Typed columns would hide the typos the gate exists to refuse. Measured
    # 2026-10-01 on dlt 1.30.0: a bigint hint landed "minutes": "34" as 34, a
    # text hint landed "title": 5 as "5", sql_ci_v1 folded a misspelt
    # "At_Miles" into at_miles, and a field null on every row made no column.
    verbatim: bool = False

    def column_hints(self) -> dict:
        hints = {name: {"data_type": data_type} for name, data_type in self.hints}
        return {**hints, "row_json": {"data_type": "text"}} if self.verbatim else hints

    @property
    def file(self) -> Path:
        return PIPELINE_DIR / self.path

    @property
    def zero_proof(self) -> str:
        """The file is its own upstream (the docstring), so the rows a person reviewed into it are its count."""
        return "the reviewed file's own rows: the file in git is its own upstream, and a missing file raises"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        if not self.file.is_file():
            return Freshness.UNKNOWN, None
        marker = {"sha256": _file_sha256(self.file)}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        document = json.loads(self.file.read_text())
        if self.rows_key is None:
            body = {name: value for name, value in document.items() if name != "_README"}
            proofs[self.table] = 1
            fields = {"row_json": json.dumps(body, ensure_ascii=False), "_row": 0} if self.verbatim else body
            yield {**fields, "_path": self.path}
            return
        rows = document[self.rows_key]
        if self.map_key is not None:
            if not isinstance(rows, dict):
                raise ValueError(f"{self.path}: {self.rows_key} is not a map, so it has no ids for {self.map_key}")
            if any(self.map_key in row for row in rows.values()):
                raise ValueError(f"{self.path}: a row already carries {self.map_key}, so the map's id cannot land there")
            rows = [{self.map_key: row_id, **row} for row_id, row in rows.items()]
        context = {name: value for name, value in document.items() if name not in ("_README", self.rows_key)}
        proofs[self.table] = len(rows)
        # `_row` is the row's place in the file, because a reviewed file's order is
        # often the published order (export_podcasts.py keeps it) and SQL has none.
        for index, row in enumerate(rows):
            fields = {"row_json": json.dumps(row, ensure_ascii=False)} if self.verbatim else row
            yield {**fields, "_row": index, "_file": context, "_path": self.path}


def reviewed_input(key: str, rows_key: str, **overrides) -> ReviewedFile:
    """A registry entry whose rows are reviewed into the file its `reviewed_input` names.

    ATC's Trail Updates is the case: the registry row is the upstream, and
    what ships today is the reviewed file (features/ATC_TRAIL_UPDATES.md, "the
    parse proposes; a human publishes"). The key is the claim, so the claim
    test sees the registry row once; the file is where the rows come from.
    """
    path = registry_entry(key).get("reviewed_input")
    if not path:
        raise KeyError(f"{key} has no reviewed_input in sources.json")
    return ReviewedFile(key=key, path=path, rows_key=rows_key, **overrides)


def reviewed_file(
    path: str,
    rows_key: str | None,
    map_key: str | None = None,
    hints: dict[str, str] | None = None,
    verbatim: bool = False,
    **overrides,
) -> ReviewedFile:
    if not (PIPELINE_DIR / path).is_file():
        raise FileNotFoundError(path)
    return ReviewedFile(
        key=path,
        path=path,
        rows_key=rows_key,
        map_key=map_key,
        hints=tuple(sorted((hints or {}).items())),
        verbatim=verbatim,
        **overrides,
    )


@dataclass(frozen=True)
class ReviewedDir(Resource):
    """A folder of reviewed files, one row per file: a club's challenges, one file per challenge.

    The marker hashes every file's name and bytes together, so adding,
    editing or removing one challenge reloads the folder.
    """

    path: str = ""
    # As ReviewedFile's `verbatim`, for a folder a gate checks field by field:
    # each file lands whole in `row_json` (`_README` left out), so a field's
    # JSON type reaches the gate. A file that is not valid JSON lands with
    # `row_json` null and the parser's complaint in `_parse_error`, as
    # export_challenges.load_challenge_files() treats it (None to its
    # resolver, the complaint printed): one broken file is dropped and named,
    # never a failed extract that holds back every other resource on its lane.
    verbatim: bool = False

    def column_hints(self) -> dict:
        return {"row_json": {"data_type": "text"}, "_parse_error": {"data_type": "text"}} if self.verbatim else {}

    @property
    def files(self) -> list[Path]:
        return sorted((PIPELINE_DIR / self.path).glob("*.json"))

    @property
    def zero_proof(self) -> str:
        return "the reviewed folder's own files: the folder in git is its own upstream"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        digest = hashlib.sha256()
        for file in self.files:
            digest.update(file.name.encode() + b"\0" + file.read_bytes() + b"\0")
        marker = {"sha256": digest.hexdigest(), "files": str(len(self.files))}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        files = self.files
        proofs[self.table] = len(files)
        for file in files:
            if self.verbatim:
                yield {**self._verbatim_row(file), "_path": str(file.relative_to(PIPELINE_DIR))}
                continue
            document = json.loads(file.read_text())
            yield {
                **{name: value for name, value in document.items() if name != "_README"},
                "_path": str(file.relative_to(PIPELINE_DIR)),
            }

    @staticmethod
    def _verbatim_row(file: Path) -> dict:
        """The file as json.loads reads it, `_README` aside, as JSON text; or null and why, for a file that does not parse.

        Parsed here and written again, rather than landed as its bytes, so a
        repeated key resolves as json.loads resolves it (the last wins), which
        is what today's resolver reads. UTF-8, as load_challenge_files() reads.
        """
        try:
            document = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            return {"row_json": None, "_parse_error": str(error)}
        if isinstance(document, dict):
            document = {name: value for name, value in document.items() if name != "_README"}
        return {"row_json": json.dumps(document, ensure_ascii=False), "_parse_error": None}


def reviewed_dir(path: str, **overrides) -> ReviewedDir:
    if not (PIPELINE_DIR / path).is_dir():
        raise FileNotFoundError(path)
    return ReviewedDir(key=path, path=path, **overrides)


# trail_orgs.json fields the sources mart reads (ELT.md: org, website, type,
# licence, licence_basis, attribution, load, via), and the licence fields of
# each key the club claims.
ORG_FIELDS = ("slug", "org", "website", "type", "licence", "licence_basis", "attribution", "load", "via")
CLAIM_FIELDS = ("licence", "licence_basis", "attribution", "reaches_hikers")
ORGS_TABLE = "raw_extract__orgs"


@lru_cache(maxsize=4)
def _trail_orgs(path: Path) -> dict:
    document = json.loads(path.read_text())
    return {row["slug"]: row for row in document["orgs"]}


@dataclass(frozen=True)
class CatalogueRow(Resource):
    """The club's trail_orgs.json row, plus the licence fields of every key the club claims.

    All clubs write one shared table, `raw_extract__orgs`, the sources mart's
    input. That is safe under `replace` only because these are local reads and
    every org resource runs on every monthly run (ELT.md, "The contract, and
    one file of each kind"); extract/_run.py never change-checks them away.
    """

    @property
    def table(self) -> str:
        return ORGS_TABLE

    @property
    def name(self) -> str:
        return f"org_{self.club}"

    @property
    def zero_proof(self) -> None:
        """None: the run check holds this shared table to exactly one row per managing club instead (run_check())."""
        return None

    def rows(self, proofs: dict[str, int]):
        slug = slug_for_folder(self.club)
        org = _trail_orgs(TRAIL_ORGS_PATH).get(slug)
        if org is None:
            raise KeyError(f"{self.club}/ has no trail_orgs.json row with slug {slug!r}")
        claims = []
        # A club with no resource file has no folder (decision 88), and so claims nothing.
        for path in sorted((EXTRACT_DIR / self.club).glob("*.py")):
            club_file = read_club_file(path)
            for key in club_file.claims:
                entry = _registry(REGISTRY_PATH).get(key, {})
                claims.append({"key": key, "type": club_file.type, **{name: entry.get(name) for name in CLAIM_FIELDS}})
        yield {**{name: org.get(name) for name in ORG_FIELDS}, "claims": claims}


def catalogue_row() -> CatalogueRow:
    return CatalogueRow(key="reference/trail_orgs.json")


# RSS and the namespaces a podcast feed's items use. Each child of an <item>
# becomes a column named by its tag, the namespace written as a short prefix
# (itunes_duration), so nothing a feed carries is dropped before dbt sees it.
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
PODCAST_INDEX = "{https://podcastindex.org/namespace/1.0}"
DUBLIN_CORE = "{http://purl.org/dc/elements/1.1/}"
GOOGLE_PLAY = "{http://www.google.com/schemas/play-podcasts/1.0}"

# An item's tags that name or reach a person, by their namespaced name, each seen on a live feed on 2026-10-04
# (extract/_content.py's module docstring): never read, so no column for them exists, by PodcastFeed or its
# subclass PodcastEpisodes. RSS 2.0 defines <author> as "Email address
# of the author of the item"; `itunes:owner` carries an owner's name and e-mail address (USFWS's Future of
# Conservation puts it on every item); Google Play's `author` repeats iTunes' (Mohonk's Walk Back in Time, a
# named individual on 12 of 12). A person under a tag nobody has named loads until it is added here, which is
# why each new feed's tags are read before its row is registered.
PERSON_TAGS = frozenset(
    {
        "author",
        f"{ITUNES}author",
        f"{ITUNES}owner",
        f"{DUBLIN_CORE}creator",
        f"{PODCAST_INDEX}person",
        f"{GOOGLE_PLAY}author",
        f"{GOOGLE_PLAY}owner",
        f"{GOOGLE_PLAY}email",
    }
)


FEED_NAMESPACES = {
    "http://www.itunes.com/dtds/podcast-1.0.dtd": "itunes",
    "http://purl.org/rss/1.0/modules/content/": "content",
    "https://podcastindex.org/namespace/1.0": "podcast",
}


def _feed_column(tag: str) -> str:
    if tag.startswith("{"):
        uri, name = tag[1:].split("}", 1)
        return f"{FEED_NAMESPACES.get(uri, 'ns')}_{name}"
    return tag


@dataclass(frozen=True)
class PodcastFeed(PersonRuled, Resource):
    """A podcast's RSS feed, one row per episode: its metadata, never its audio.

    Change check: a conditional GET with the feed's own validators; a 304 is
    FRESH. On a safety path a feed may only signal a change, because an RSS
    window is not a list of current items (ELT.md, "The skip-unchanged check,
    by platform"). Podcasts are not a safety path, and a podcast feed lists the
    whole show: The Green Tunnel's held 51 items against Apple's count of 51
    episodes (2026-10-01). Each episode's `guid` is the key it is staged on
    (51 of 51 unique, the same day).

    An <enclosure> is kept as its URL, length and type, and is never fetched.
    """

    @property
    def entry(self) -> dict:
        return registry_entry(self.key)

    @property
    def zero_proof(self) -> str:
        """An RSS channel's items, from the same answer as the rows; a body with no <channel> raises (rows())."""
        return "the RSS <channel>'s own items, in the answer the rows come from; a body with no <channel> raises"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        headers = {}
        if recorded:
            if recorded.get("etag"):
                headers["If-None-Match"] = recorded["etag"]
            if recorded.get("last_modified"):
                headers["If-Modified-Since"] = recorded["last_modified"]
        try:
            response = request_with_retry(self.entry["url"], session=session(), headers=headers or None, timeout=30)
        except requests.RequestException as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if response.status_code == 304:
            return Freshness.FRESH, recorded
        marker = {"etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified")}
        if not marker["etag"] and not marker["last_modified"]:
            return Freshness.UNKNOWN, None
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        response = request_with_retry(self.entry["url"], session=session(), timeout=60)
        channel = ElementTree.fromstring(response.content).find("channel")
        if channel is None:
            raise ValueError(f"{self.key}: the answer is not an RSS feed (no <channel>)")
        items = channel.findall("item")
        proofs[self.table] = len(items)
        show = {"show_title": channel.findtext("title"), "show_link": channel.findtext("link")}
        episodes = []
        for item in items:
            row = {}
            for child in item:
                if child.tag in PERSON_TAGS:
                    continue
                column = _feed_column(child.tag)
                if column == "enclosure":
                    row["enclosure_url"] = child.get("url")
                    row["enclosure_length"] = child.get("length")
                    row["enclosure_type"] = child.get("type")
                else:
                    row[column] = (child.text or "").strip() or None
            episodes.append(row)
        for row in self.without_people(episodes):
            yield {**show, **row}


def podcast_feed(key: str, **overrides) -> PodcastFeed:
    entry = registry_entry(key)
    if source_kind(entry) != PODCAST_FEED:
        raise ValueError(f"{key} is a {source_kind(entry)}, not a {PODCAST_FEED}")
    return PodcastFeed(key=key, **overrides)


# ATC's robots.txt asks every agent to wait between requests: `User-agent: *`,
# `Disallow: /wp-admin/`, `Crawl-delay: 10` (read 2026-10-02, 190 bytes).
# lib/atc_scrape.py's fetcher sends its listing pages without waiting (the dlt
# skill, "Honour Crawl-delay"); every request this resource sends ATC waits it,
# through ATC_CRAWL_GATE below. Fixture mode sets it to 0, as it serves no host
# (extract/_fixtures.py).
ATC_CRAWL_DELAY_SECONDS = 10

# The sitemap protocol's namespace, which ATC's All in One SEO sitemap declares (read 2026-10-02).
SITEMAP_NAMESPACE = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# How long the read reuses the sitemap the change check fetched in the same
# run, instead of asking again. ATC serves it with `cache-control: max-age=600`
# through Cloudflare and WP Engine (measured 2026-10-02 18:13 UTC: the body
# "generated" 11 minutes before it was served), so a re-read sooner than that
# can return the same copy.
ATC_LISTING_REUSE_SECONDS = 600

# The time one page read is allowed beyond the Crawl-delay's wait, when the
# read has a budget: no page is started that this much time would not see
# finish. Reasoned from a full crawl of 2026-10-02 (98 requests, every one 200,
# 1,062 s at 10 s apart, so about 0.9 s each beyond the wait): 15 s is about
# 16 times that. A slower page still finishes; only a read that overruns the
# whole budget the run gives it is abandoned (extract/_run.py's read_each).
ATC_PAGE_ALLOWANCE_SECONDS = 15

# Kept back from the read's budget for what follows the last page (building
# the rows) and for the read_each thread's own start. @unvalidated: a round
# number; what would settle it is the UA soak's summaries (decision 30),
# which time the read and would show whether the margin is ever needed.
ATC_READ_MARGIN_SECONDS = 5

# How many runs it takes to re-read every carried page once when nothing
# moves, so a page whose text changed while its lastmod stayed put is read
# again within that many runs (AtcTrailUpdatePages, "LASTMOD IS NOT EVERY
# CHANGE"). 24 is one day of the hourly lane, the 24 h a page stayed trusted
# in lib/atc_scrape.py's CACHE_TTL, so the gap is no wider than today's
# fetcher leaves it. @unvalidated: what would settle it is how often a
# re-read finds a page changed while its lastmod stood still, which this
# resource prints each time it does.
ATC_REVALIDATION_RUNS = 24


@dataclass
class CrawlGate:
    """One host's Crawl-delay, kept between one request's end and the next request's start, whoever sends them.

    Every request this resource sends ATC passes wait() before and done()
    after (gated() below), across sessions, the change check and the read,
    and each attempt lib/http_retry.py makes, so no two are closer than the
    delay, a failed one included. A gap is measured end to start, the
    stricter reading of a Crawl-delay. `clock` and `sleep` are what a test
    replaces to assert a delay and a budget without waiting them out; None
    is time.monotonic and time.sleep, looked up when used.
    """

    clock: object = None
    sleep: object = None
    finished: float | None = None

    def now(self) -> float:
        return (self.clock or time.monotonic)()

    def remaining(self) -> float:
        """Seconds still to wait before the next request may start: 0 once the delay has passed."""
        if self.finished is None:
            return 0.0
        return max(0.0, self.finished + ATC_CRAWL_DELAY_SECONDS - self.now())

    def wait(self) -> None:
        pause = self.remaining()
        if pause > 0:
            (self.sleep or time.sleep)(pause)

    def done(self) -> None:
        self.finished = self.now()


ATC_CRAWL_GATE = CrawlGate()

# The sitemap each change check read, by key, with the gate clock's time it
# was read, for the read that follows in the same run (ATC_LISTING_REUSE_SECONDS).
_ATC_LISTINGS: dict[str, tuple[float, list[tuple[str, str | None]]]] = {}


def gated(http: requests.Session) -> requests.Session:
    """`http`, with every request it sends held to ATC_CRAWL_GATE, the attempts lib/http_retry.py retries included."""
    send = http.request

    def request(*args, **kwargs):
        ATC_CRAWL_GATE.wait()
        try:
            return send(*args, **kwargs)
        finally:
            ATC_CRAWL_GATE.done()

    http.request = request
    return http


def _atc_sitemap_url(entry: dict) -> str:
    """The post type's sitemap beside the registry row's listing: `/trail-updates/` is read from `/trail-updates-sitemap.xml`.

    All in One SEO names each post type's sitemap `<type>-sitemap.xml` at the
    site's root (the sitemap's own stylesheet line reads `?sitemap=trail-updates`,
    read 2026-10-02), so the URL is derived from the row's `url`, as `_wp_api`
    derives a WordPress site's REST root, and the registry stays its one home.
    """
    parsed = urlparse(entry["url"])
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 1:
        raise KeyError(f"{entry['key']}: url is not a one-segment listing page, so it has no sitemap beside it: {entry['url']}")
    return f"{parsed.scheme}://{parsed.netloc}/{parts[0]}-sitemap.xml"


def _instant(stamp: str | None) -> datetime | None:
    """An ISO stamp with its offset as an aware instant, or None where it has none or Python cannot read it."""
    try:
        parsed = datetime.fromisoformat(stamp) if stamp else None
    except ValueError:
        return None
    return parsed if parsed is None or parsed.tzinfo is not None else None


def page_behind_sitemap(row: dict) -> bool:
    """Whether the page a row was parsed from was older than the sitemap entry it was read for.

    A page's latest stamp (the later of its JSON-LD dateModified and
    datePublished) equalled the sitemap's lastmod on all 86 pages of a full
    crawl (measured 2026-10-02, 04:42-05:00 UTC; dateModified alone on 85,
    helene-storm-damage carrying a datePublished of 2026-07-29 after a
    dateModified of 2025-09-23). So a page older than its lastmod came from a
    cache that had not caught up with the sitemap: Cloudflare's edge caches the
    sitemap and each page apart, each with `cache-control: max-age=600`
    (measured 2026-10-02: the sitemap at 18:13 UTC,
    harpers-ferry-footbridge-closure at 18:59 UTC, `cf-cache-status: HIT`).
    False where either stamp cannot be read, since that proves nothing.
    """
    stamps = [stamp for stamp in (_instant(row.get("date_modified")), _instant(row.get("date_published"))) if stamp]
    lastmod = _instant(row.get("sitemap_lastmod"))
    return bool(stamps) and lastmod is not None and max(stamps) < lastmod


# Each row's own columns, as rows_carried() yields them: what a carried row is
# cut back to, so dlt's columns and `_loaded_at` from its last load never ride
# along. `_row` is not one: it is the update's place in this run's sitemap.
ATC_PAGE_COLUMNS = (
    "slug",
    "title",
    "category",
    "states",
    "date_modified",
    "date_published",
    "miles",
    "source_url",
    "sitemap_lastmod",
    "page_sha256",
    "page_fetched_at",
)
# The columns that land as JSON text, which a row read back from the table's
# Parquet holds as a string (the dlt skill, rule 1) and a parsed page as a list.
ATC_PAGE_JSON_COLUMNS = ("states", "miles")
# What a re-read compares, to tell a page whose facts changed while its lastmod
# did not: everything but when it was read and the hash of the bytes, which
# moves with ATC's markup alone.
ATC_PAGE_FACTS = tuple(name for name in ATC_PAGE_COLUMNS if name not in ("page_fetched_at", "page_sha256"))


def _page_row(row: dict) -> dict:
    """A row as rows_carried() yields it, from a parsed page, a committed load's Parquet or a progress row."""
    kept = {name: row.get(name) for name in ATC_PAGE_COLUMNS}
    for name in ATC_PAGE_JSON_COLUMNS:
        if isinstance(kept[name], str):
            kept[name] = json.loads(kept[name])
    return kept


@dataclass(frozen=True)
class AtcTrailUpdatePages(Resource):
    """ATC's Trail Updates read off their website: one row per update their trail-updates sitemap lists.

    The parse is lib/atc_scrape.py's parse_update(), unchanged, because ELT.md
    puts an HTML scrape in extraction ("What stays outside dbt", CL11). Whether
    a row may publish without a person is dbt's call
    (int_closures__atc_automatic, CL07-CL10), never this resource's.

    THE SITEMAP, NOT THE LISTING (ELT.md, "The skip-unchanged check, by
    platform"). The listing cannot show an edit, so fetch_atc_updates.py walks
    its ten pages hourly and re-reads every update daily (lib/atc_scrape.py's
    CACHE_TTL); the sitemap carries each URL's `lastmod`. Its slug set equalled
    the listing's on both days compared (86 = 86, 2026-10-01 and 2026-10-02),
    so an update ATC stops listing leaves this table and is not republished
    (CL10).

    ONLY WHAT MOVED IS READ, AND THE WHOLE TABLE STILL LANDS. Each run reads the
    sitemap, then, at the full Crawl-delay, the page of each update that is new
    or whose lastmod moved since the last committed load. Every other row is
    carried from that load (Carried.committed) and an unlisted slug is
    dropped. The whole set lands under `replace`, so a refused load, a skipped
    run and the run check behave as for any table. Reading every page whenever
    the set moved froze the table: 87 requests 10 s apart is about 15 minutes
    (Reasoned), and the conditions leg gives a read 150 s
    (publish-conditions.yml's `--read-seconds`).
    tests/test_extract_atc_trail_update_pages.py holds an incremental read
    after a change equal to a full read of the same pages.

    A READ THAT RUNS OUT OF BUDGET LANDS NOTHING (Incomplete): a partial set
    under `replace` reads as the whole, so an update not reached yet would read
    as one ATC took down. What it read is kept as progress, never as data
    (extract/_run.py's `_extract_progress`), and the next run carries it, so a
    first run on an empty raw store takes about 8 runs (86 pages at about 12 a
    run; Reasoned from ATC_PAGE_ALLOWANCE_SECONDS' figures). Until every moved
    page is read, the last committed table stands.

    LASTMOD IS NOT EVERY CHANGE. It moves with the post's modified and
    published dates only (page_behind_sitemap() has the measurement), not when
    a state or category term the page shows is renamed, a field is written
    without a save, or the theme changes the page. So, in the budget the moved
    pages leave, each run re-reads any page that was behind its lastmod when
    read, then the pages read longest ago, enough to cover every page within
    ATC_REVALIDATION_RUNS runs, and prints any re-read whose facts changed
    while its lastmod did not. ATC's cache serves the sitemap for up to 600 s
    (ATC_LISTING_REUSE_SECONDS), so an edit can take that long to reach the
    change check.

    THE CHECK reads the sitemap (27,252 bytes on 2026-10-02; ELT.md measured
    3,411 on 2026-10-01) and is never FRESH, because every run has pages to
    re-read; its marker hashes the (slug, lastmod) set. About 5 requests an
    hour, 10 s apart, against about 350 a day today with no delay (Reasoned:
    the sitemap, ceil(86 / 24) = 4 re-reads, and about one moved page a day,
    as two reads of the sitemap 38 hours apart found: one lastmod moved,
    nothing added or removed, 2026-10-01 03:53 to 2026-10-02 18:13 UTC).

    WHAT DOES NOT LAND: ATC's prose. The parse's `text` is the update's body,
    which no rule reads and sources.json's licence keeps on ATC's page ("Facts
    and a link only, and NOT a grant to mirror ATC's prose"); the page itself
    belongs in the as-sent copy, not built yet. `page_sha256` (provenance) and
    `page_fetched_at` land instead, and a carried row keeps both.

    A READ THAT FAILS, FAILS LOUDLY. An empty sitemap is a broken read, never
    "ATC has nothing posted" (fetch_atc_updates.py's rule), and one page that
    does not parse (TOLERATED_PARSE_FAILURES, zero) or answer refuses the
    whole read, so the last committed table stands, as today's cache does. The
    proof is the sitemap's own slug count, which the landed rows must equal
    (`exact_proof`; ELT.md, "A full reload that cannot empty a safety table").
    """

    @property
    def table(self) -> str:
        return super().table + "_pages"

    @property
    def part(self) -> str:
        return "pages"

    @property
    def carries(self) -> bool:
        return True

    @property
    def exact_proof(self) -> bool:
        return True

    @property
    def zero_proof(self) -> str:
        """The sitemap's slug count (the docstring's last paragraph); an empty sitemap raises before any zero."""
        return "the slug count of ATC's trail-updates sitemap; an empty sitemap raises before any zero"

    @property
    def entry(self) -> dict:
        return registry_entry(self.key)

    @property
    def sitemap_url(self) -> str:
        return _atc_sitemap_url(self.entry)

    def _get(self, http: requests.Session, url: str, label: str) -> requests.Response:
        return request_with_retry(url, session=http, timeout=60, label=label)

    def sitemap(self, http: requests.Session) -> list[tuple[str, str | None]]:
        """(slug, lastmod) for each update the sitemap lists, in its order, each slug once.

        Raises on a URL that is not a trail update's own page, because a
        sitemap listing something else has changed shape.
        """
        root = ElementTree.fromstring(self._get(http, self.sitemap_url, "ATC trail-updates sitemap").content)
        listing = self.entry["url"]
        found: dict[str, str | None] = {}
        for url in root.findall("s:url", SITEMAP_NAMESPACE):
            loc = (url.findtext("s:loc", default="", namespaces=SITEMAP_NAMESPACE) or "").strip()
            slug = loc[len(listing) :].rstrip("/") if loc.startswith(listing) else ""
            if not re.fullmatch(r"[a-z0-9-]+", slug) or atc_update_url(slug) != loc:
                raise ValueError(f"{self.key}: the sitemap lists {loc!r}, which is not a trail update's page")
            lastmod = (url.findtext("s:lastmod", default="", namespaces=SITEMAP_NAMESPACE) or "").strip()
            found.setdefault(slug, lastmod or None)
        return list(found.items())

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        _ATC_LISTINGS.pop(self.key, None)
        try:
            listed = self.sitemap(gated(session()))
        except (requests.RequestException, ValueError, ElementTree.ParseError) as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if not listed:
            # The read runs, and refuses on the empty sitemap.
            return Freshness.UNKNOWN, None
        _ATC_LISTINGS[self.key] = (ATC_CRAWL_GATE.now(), listed)
        marker = {"slugs": str(len(listed)), "set_sha256": hashlib.sha256(json.dumps(sorted(listed)).encode()).hexdigest()}
        # Never FRESH, even on an unchanged set: the read re-reads the pages read longest ago ("LASTMOD IS NOT
        # EVERY CHANGE" above), which a run left out of the lane would never reach.
        return Freshness.STALE, marker

    def column_hints(self) -> dict:
        # Every stamp stays text: dlt reads an ISO stamp as a timestamp and
        # normalises it to UTC (NWS_TEXT_PROPERTIES above), which would lose
        # the offset dateModified carries.
        texts = (
            "slug",
            "title",
            "category",
            "date_modified",
            "date_published",
            "source_url",
            "sitemap_lastmod",
            "page_sha256",
            "page_fetched_at",
        )
        hints = {name: {"data_type": "text"} for name in texts}
        hints.update({"states": {"data_type": "json"}, "miles": {"data_type": "json"}, "_row": {"data_type": "bigint"}})
        return hints

    def rows(self, proofs: dict[str, int]):
        """A full read: every page the sitemap lists, nothing carried and no budget."""
        yield from self.rows_carried(proofs, Carried())

    def _listing(self, http: requests.Session) -> list[tuple[str, str | None]]:
        """The sitemap the change check read in this run, while still that young, or a fresh read of it."""
        reused = _ATC_LISTINGS.pop(self.key, None)
        if reused is not None and ATC_CRAWL_GATE.now() - reused[0] <= ATC_LISTING_REUSE_SECONDS:
            return reused[1]
        return self.sitemap(http)

    def _read_page(self, http: requests.Session, slug: str, lastmod: str | None) -> dict | None:
        """One update's page as its row, or None when it does not parse."""
        response = self._get(http, atc_update_url(slug), f"ATC trail update {slug}")
        parsed = parse_atc_update(response.text, slug)
        if parsed is None:
            return None
        return {
            "slug": parsed.slug,
            "title": parsed.title,
            "category": parsed.category,
            "states": list(parsed.states),
            "date_modified": parsed.date_modified,
            "date_published": parsed.date_published,
            "miles": [{"direction": m.direction, "start": m.start, "end": m.end, "raw": m.raw} for m in parsed.miles],
            "source_url": parsed.source_url,
            "sitemap_lastmod": lastmod,
            "page_sha256": hashlib.sha256(response.content).hexdigest(),
            "page_fetched_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }

    def rows_carried(self, proofs: dict[str, int], carried: Carried):
        gate = ATC_CRAWL_GATE
        deadline = None if carried.seconds is None else gate.now() + carried.seconds - ATC_READ_MARGIN_SECONDS

        def time_for_one_more() -> bool:
            return deadline is None or gate.now() + gate.remaining() + ATC_PAGE_ALLOWANCE_SECONDS <= deadline

        http = gated(session())
        listed = self._listing(http)
        if not listed:
            raise RuntimeError(f"{self.key}: ATC's trail-updates sitemap lists no update, which means the read broke")
        lastmods = dict(listed)

        # What may be carried: a row whose sitemap entry has not moved since its page was read. A slug listed
        # with no lastmod is never carried, since nothing says it did not move. Where the committed load and
        # the progress both hold one, the later read wins.
        known: dict[str, dict] = {}
        from_progress: set[str] = set()
        for origin, rows in (("committed", carried.committed), ("progress", carried.progress)):
            for raw in rows:
                row = _page_row(raw)
                slug = row["slug"]
                if lastmods.get(slug) is None or row["sitemap_lastmod"] != lastmods[slug]:
                    continue
                if slug not in known or (row["page_fetched_at"] or "") > (known[slug]["page_fetched_at"] or ""):
                    known[slug] = row
                    if origin == "progress":
                        from_progress.add(slug)
                    else:
                        from_progress.discard(slug)
        due = [slug for slug, _ in listed if slug not in known]

        fetched: dict[str, dict] = {}
        failures: list[str] = []
        for slug in due:
            if not time_for_one_more():
                break
            row = self._read_page(http, slug, lastmods[slug])
            if row is None:
                failures.append(slug)
            else:
                fetched[slug] = row
        unread = [slug for slug in due if slug not in fetched and slug not in failures]

        if not unread and not failures:
            # Every moved page is read, so what budget is left re-reads the carried pages: first any that was
            # older than its lastmod when read, then those read longest ago, a share each run sized to reach
            # every page within ATC_REVALIDATION_RUNS runs.
            share = -(-len(listed) // ATC_REVALIDATION_RUNS)
            behind = [slug for slug, _ in listed if slug in known and page_behind_sitemap(known[slug])]
            oldest = sorted(
                (slug for slug in known if slug not in behind), key=lambda slug: (known[slug]["page_fetched_at"] or "", slug)
            )
            for slug in behind[:share] + oldest[:share]:
                if not time_for_one_more():
                    break
                row = self._read_page(http, slug, lastmods[slug])
                if row is None:
                    failures.append(slug)
                    continue
                # A page that was behind its lastmod was expected to change; any other is the hazard's evidence.
                if slug not in behind and any(row[name] != known[slug][name] for name in ATC_PAGE_FACTS):
                    stood = f"{slug}'s facts changed while its lastmod stood at {lastmods[slug]}"
                    print(f"::warning title={self.key} page changed without its lastmod::{stood}; the re-read lands")
                fetched[slug] = row

        if len(failures) > ATC_TOLERATED_PARSE_FAILURES:
            raise RuntimeError(
                f"{self.key}: {len(failures)} of {len(listed)} update pages did not parse ({', '.join(failures[:5])}), "
                "which is ATC's page changing shape; nothing lands rather than the updates that still parsed"
            )
        if unread and not fetched:
            raise RuntimeError(
                f"{self.key}: the read's {carried.seconds:g} s budget fit none of the {len(due)} update pages it needs, "
                "so it would never complete; that is a budget too small for one page at ATC's Crawl-delay"
            )
        if unread:
            progress = [known[slug] for slug, _ in listed if slug in from_progress] + list(fetched.values())
            raise Incomplete(
                f"{self.key}: read {len(fetched)} of the {len(due)} update pages this sitemap needs read "
                f"({len(unread)} left, {len(known)} carried) before the budget ran out; nothing lands until all are read",
                progress=progress,
                read=len(fetched),
                needed=len(unread),
            )
        proofs[self.table] = len(listed)
        for position, (slug, _) in enumerate(listed):
            yield {**(fetched.get(slug) or known[slug]), "_row": position}


def atc_trail_update_pages(key: str, **overrides) -> AtcTrailUpdatePages:
    resource = AtcTrailUpdatePages(key=key, **overrides)
    resource.sitemap_url  # a registry url with no sitemap beside it fails at import, in the layout test
    return resource
