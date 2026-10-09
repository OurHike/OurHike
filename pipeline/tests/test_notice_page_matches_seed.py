"""Decision 128's two seeds, held to the registry, the extract and each other.

Parks & Trails New York's closures layer (ptny_est_closures) says 'Closed' on
all nine of its Empire State Trail sections with no date, reason or link. The
maintainer chose, by poll on 2026-10-09 (w6-ptny-closures.html, frame A), that
a section may draw as closed only once a person has matched it to an item on
the trail's dated closures page, and only while that page still carries the
item. dbt/seeds/notice_confirming_pages.csv names the source and its page;
dbt/seeds/notice_page_matches.csv holds the matches, each approved by the
maintainer in chat before it is written (decision 121's rule), so it ships
with none and nothing draws.

What no dbt test can see is held here: the registry's `reaches_hikers` moves
with the matches, the page is one the extract reads item by item, and each
row says where it was approved without naming anybody.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import yaml

PIPELINE = Path(__file__).resolve().parents[1]
SEEDS = PIPELINE / "dbt" / "seeds"
CLOSURES_YAML = PIPELINE / "dbt" / "models" / "intermediate" / "closures" / "_closures__intermediate.yml"
REGISTRY = {row["key"]: row for row in json.loads((PIPELINE / "sources.json").read_text())["sources"]}
RULE_7_TEST = "int_closures__club_notices_draws_a_confirming_sources_row_only_while_its_page_match_stands"


def seed(name: str) -> list[dict]:
    with (SEEDS / f"{name}.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def pages() -> dict[str, str]:
    """Each confirming source and the page its rows are matched to."""
    return {row["source_key"]: row["page_source_key"] for row in seed("notice_confirming_pages")}


def matches() -> list[dict]:
    return seed("notice_page_matches")


def source_of(notice_id: str) -> str:
    return notice_id.split(":", 1)[0]


def test_decision_128_names_ptny_closed_sections_and_the_trails_closures_page():
    assert pages() == {"ptny_est_closures": "oprhp_est_trail_closures_page"}


def test_a_confirming_source_reaches_hikers_exactly_when_a_match_is_approved():
    """With no match, nothing of PTNY's draws, so the registry keeps it held and stewards.json does not list PTNY as
    a source of a map that carries none of its data; the commit that writes the first approved match sets it true.
    Either half alone is a mistake: a match that can never draw, or an organization credited for nothing."""
    matched = {source_of(row["notice_id"]) for row in matches()}
    for source, _page in pages().items():
        assert REGISTRY[source]["reaches_hikers"] is (source in matched), (
            f"{source}: reaches_hikers must be true exactly while notice_page_matches.csv holds a match for it"
        )


def test_each_confirming_page_reaches_hikers_and_is_read_item_by_item():
    """A match stands only on a page that may publish, and only one whose read lands each item's sha256."""
    from extract.nysparks import closures

    read_with_items = {resource.key for resource in closures.RESOURCES if getattr(resource, "items", None)}
    for page in pages().values():
        assert REGISTRY[page]["reaches_hikers"] is True, page
        assert page in read_with_items, f"{page} is not read with `items`, so no match to it could ever stand"


def test_every_match_names_a_row_of_a_confirming_source_and_that_sources_own_page():
    for row in matches():
        source = source_of(row["notice_id"])
        assert source in pages(), f"{row['notice_id']}: {source} is not a source notice_confirming_pages.csv names"
        assert row["page_source_key"] == pages()[source], row["notice_id"]


def test_every_match_says_where_it_was_approved_and_names_nobody():
    """`reviewed_in` is the pull request that records the maintainer's approval, by number and title (CLAUDE.md), and
    never a person: a reviewer's name or address in a public seed is a person field published (CONTRIBUTING.md)."""
    for row in matches():
        assert re.search(r"#\d+ — \S", row["reviewed_in"]), f"{row['notice_id']}: {row['reviewed_in']!r}"
        assert "@" not in row["reviewed_in"] + row["evidence"], row["notice_id"]
        assert re.fullmatch(r"[0-9a-f]{64}", row["page_item_sha256"]), row["notice_id"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["matched_on"]), row["notice_id"]


def test_the_rule_7_unit_test_mocks_the_pairs_the_seed_file_holds():
    """So the unit test cannot pass on a pairing the build does not use (tests/test_dbt_closures_club_notices.py's
    reason, for the status seed)."""
    tests = {test["name"]: test for test in yaml.safe_load(CLOSURES_YAML.read_text())["unit_tests"]}
    (given,) = [g for g in tests[RULE_7_TEST]["given"] if g["input"] == "ref('notice_confirming_pages')"]
    assert {row["source_key"]: row["page_source_key"] for row in given["rows"]} == pages()
