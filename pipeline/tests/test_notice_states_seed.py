"""Decision 76's seed, dbt/seeds/notice_states.csv, held to the registry it was read from.

A state-wide agency notice is placed by its state (the maintainer's poll,
2026-10-04): the phone shows BLM's Utah fire restrictions to a hike planned
in Utah that walks BLM's trails, and never to a Colorado hike. Which state a
source speaks for is read from the source's own data, and a wrong row shows a
hiker another state's restrictions, or hides their own. So every row has to
point at something a reviewer can check without opening the page: the
state's name or code in the source's own key or URL, and each quotation in
`evidence` verbatim on the source's sources.json row.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parents[1]
SEED = PIPELINE / "dbt" / "seeds" / "notice_states.csv"
READERS = PIPELINE / "dbt" / "seeds" / "notice_readers.csv"
REGISTRY = {row["key"]: row for row in json.loads((PIPELINE / "sources.json").read_text())["sources"]}

#: The USPS codes of the 50 states and DC, and each one's name: public facts, not data from any upstream.
STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}  # fmt: skip


def seed_rows() -> list[dict]:
    with SEED.open(newline="") as handle:
        return list(csv.DictReader(handle))


def kinds() -> dict[str, str]:
    with READERS.open(newline="") as handle:
        return {row["source_key"]: row["steward_kind"] for row in csv.DictReader(handle)}


def tokens(text: str) -> set[str]:
    """The words of a key or URL, split on what separates them there."""
    return set(re.split(r"[^a-z0-9]+", text.lower())) - {""}


def test_the_seed_holds_the_thirteen_state_wide_notices_decision_76_found():
    """BLM's 12 state fire-restriction pages and CT DEEP's emergency message, of the 22 unplaced agency notices
    UA's live notices.json held on 2026-10-04 (generated 20:32:13Z, read 21:44Z)."""
    keys = [row["source_key"] for row in seed_rows()]
    assert len(keys) == len(set(keys)) == 13
    assert sum(key.startswith("blm_fire_restrictions_") for key in keys) == 12
    assert "ct_deep_parks_emergency_message" in keys
    # The national alerts page and the one-park, one-city and one-district pages are not state-wide.
    for not_state_wide in ("blm_alerts", "alaska_state_parks_conditions", "nc_parks_mount_mitchell_alerts", "duluth_parks_news"):
        assert not_state_wide not in keys


@pytest.mark.parametrize("row", seed_rows(), ids=lambda row: row["source_key"])
def test_each_row_is_an_agency_notice_source_the_registry_holds(row):
    entry = REGISTRY.get(row["source_key"])
    assert entry is not None, f"{row['source_key']} is not a sources.json key"
    assert entry["kind"] == "published_notices"
    assert kinds().get(row["source_key"]) == "agency", (
        "a club's unplaced notice already shows to a hike on its trails (decision 68); the seed is for agencies"
    )


@pytest.mark.parametrize("row", seed_rows(), ids=lambda row: row["source_key"])
def test_each_state_is_named_by_the_sources_own_key_or_url(row):
    """The state's name (`new-mexico`, `north_dakota`) or its code (`ct`) is a word of the key or the URL."""
    entry = REGISTRY[row["source_key"]]
    words = tokens(row["source_key"]) | tokens(entry["url"])
    for code in row["states"].split(" "):
        assert code in STATES, f"{code} is not a USPS state code"
        name = set(STATES[code].lower().split())
        assert name <= words or code.lower() in words, f"{row['source_key']}: nothing in its key or URL names {code}"


@pytest.mark.parametrize("row", seed_rows(), ids=lambda row: row["source_key"])
def test_each_quotation_in_the_evidence_is_on_the_sources_row(row):
    entry = json.dumps(REGISTRY[row["source_key"]], ensure_ascii=False)
    quotations = re.findall(r"'([^']+)'", row["evidence"])
    assert quotations, f"{row['source_key']}: its evidence quotes nothing"
    for quotation in quotations:
        assert quotation in entry, f"{row['source_key']}: {quotation!r} is not on its sources.json row"
