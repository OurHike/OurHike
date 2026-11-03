"""The readers a registry row can name, and how a row's `extract` field becomes Resources.

A sources.json row that the extract reads carries one field, `extract`:

    "extract": {"org": "amc", "type": "closures",
                "reads": [{"reader": "page_notice", "wp_page": 27, "crawl_delay": 3.0}]}

`org` is the club's folder name (its trail_orgs.json slug with `-` written
`_`), `type` is one of the ten types it answers, and each entry of `reads` is
one Resource: the builder named by `reader`, called with the row's key and
every other field of the entry as a keyword argument. A key read two ways
(a WordPress site's posts and its taxonomy terms) has two entries. `same_as`,
when present, lists republished copies of this row's dataset that are noted
and never loaded (extract/_contract.py's SameAs).

A reviewed OurHike file under pipeline/reference/ has no sources.json row, so
its club's trail_orgs.json row lists it in `reviewed_files`, with the same
`type` and `reads`, and `path` in place of the key.

JSON has no tuple, so a list in an entry is passed as a tuple, which is what
every builder was written for. A `date_pattern` may write `{DATE}` for
extract/_notices.py's DATE, the date regex every page notice reads, rather
than repeat its text.
"""

from __future__ import annotations

from dataclasses import replace

from extract._content import (
    mediawiki_template_pages,
    nps_content,
    podcast_episodes,
    site_terms,
    wordpress_child_pages,
)
from extract._contract import Resource
from extract._gis_files import gis_file
from extract._json_apis import (
    dcnr_park_advisories,
    mediawiki_announcements,
    my_maps_placemarks,
    nps_alerts,
    nps_road_events,
    sheet_csv_segments,
)
from extract._kinds import (
    arcgis_layer,
    atc_trail_update_pages,
    club_pdf,
    guide_pages,
    podcast_feed,
    published_hikes,
    reviewed_dir,
    reviewed_file,
    reviewed_input,
    socrata_dataset,
    wordpress_posts,
    wordpress_terms,
)
from extract._notices import DATE, feed_notices, page_notice
from extract._ogc import json_features
from extract._pages_content import content_pages
from extract._pages_points import page_points
from extract._pdf_content import content_pdf
from extract._pdf_points import pdf_points
from extract._sheet_content import content_sheet

READERS = {
    builder.__name__: builder
    for builder in (
        arcgis_layer,
        atc_trail_update_pages,
        club_pdf,
        content_pages,
        content_pdf,
        content_sheet,
        dcnr_park_advisories,
        feed_notices,
        gis_file,
        guide_pages,
        json_features,
        mediawiki_announcements,
        mediawiki_template_pages,
        my_maps_placemarks,
        nps_alerts,
        nps_content,
        nps_road_events,
        page_notice,
        page_points,
        pdf_points,
        podcast_episodes,
        podcast_feed,
        published_hikes,
        reviewed_dir,
        reviewed_file,
        reviewed_input,
        sheet_csv_segments,
        site_terms,
        socrata_dataset,
        wordpress_child_pages,
        wordpress_posts,
        wordpress_terms,
    )
}

# The fields of an `extract` value, and of one entry of `reviewed_files`. Anything else is refused, because a
# misspelt `reads` would otherwise build nothing without a sound.
EXTRACT_FIELDS = frozenset({"org", "type", "reads", "same_as"})
REVIEWED_FIELDS = frozenset({"path", "type", "reads"})


def _value(name: str, value):
    if isinstance(value, list):
        return tuple(_value(name, item) for item in value)
    if name == "date_pattern" and isinstance(value, str):
        return value.replace("{DATE}", DATE)
    return value


def build(key: str, read: dict, org: str, type_: str) -> Resource:
    """One entry of `reads`, built for `key` and placed in `org`'s `type_`. An unknown reader names the row."""
    options = {name: _value(name, value) for name, value in read.items() if name != "reader"}
    builder = READERS.get(read.get("reader"))
    if builder is None:
        raise ValueError(f"{key}: reader {read.get('reader')!r} is not one of {sorted(READERS)}")
    return replace(builder(key, **options), club=org, type=type_)
