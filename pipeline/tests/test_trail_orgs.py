"""The trail-organization catalogue says what it means (#1543).

`pipeline/reference/trail_orgs.json` is 163 organizations and the verdict on
each: ship it, hold it, take it through another row, refuse it, or record that
there is nothing to take. features/ORG_BULK_LOAD.md is the argument; this file
is what stops the argument drifting away from the data.

WHY THESE CHECKS AND NOT A SCHEMA. Every assertion here is one a reviewer would
otherwise have to make by eye across 163 rows, and each has a failure that has
already happened somewhere in this repository: a pointer to a row that does not
exist, a source registered without the licence question being asked, a verdict
word that means one thing in the file and another in the document beside it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CATALOGUE = Path(__file__).resolve().parents[1] / "reference" / "trail_orgs.json"

LOAD_VERDICTS = {"ship", "hold", "via", "refuse", "none"}
LICENCE_BASES = {"public_domain", "stated_by_org", "maintainer_authorisation", "unstated"}


@pytest.fixture(scope="module")
def catalogue() -> dict:
    return json.loads(CATALOGUE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def orgs(catalogue) -> list[dict]:
    return catalogue["orgs"]


def test_every_org_has_a_slug_no_two_orgs_share_one(orgs):
    """The slug is the dedupe key features/ORG_ONBOARDING.md leaves undecided.

    Two rows sharing one is how a bulk load writes a duplicate into the file
    the build reads - and the catalogue carries the Appalachian Mountain Club
    twice on purpose, so 'just deduplicate by name' is not available.
    """
    slugs = [org["slug"] for org in orgs]
    duplicated = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    assert duplicated == [], f"these slugs appear on more than one row: {duplicated}"


def test_every_load_verdict_is_one_the_file_defines(orgs, catalogue):
    """A verdict the document does not define is a verdict nobody can act on."""
    assert set(catalogue["_load_values"]) == LOAD_VERDICTS
    unknown = sorted({o["load"] for o in orgs} - LOAD_VERDICTS)
    assert unknown == [], f"verdicts nothing defines: {unknown}"


def test_every_via_pointer_names_a_row_that_is_in_this_file(orgs):
    """59 organizations hold no geometry and point at another row for it.

    A pointer to a slug that is not here reads as 'already covered' and covers
    nothing - the Maine Appalachian Trail Club's 267 miles would silently
    depend on a row that does not exist.
    """
    slugs = {org["slug"] for org in orgs}
    dangling = sorted(f"{org['slug']} -> {org['via']}" for org in orgs if org["load"] == "via" and org["via"] not in slugs)
    assert dangling == [], f"via pointers with no destination: {dangling}"


def test_a_row_that_ships_carries_an_endpoint_and_an_attribution(orgs):
    """`ship` means a fetch happens, so the two fields a fetch needs must be there.

    Attribution is required even where the licence is unstated: an organization
    that never stated terms did not thereby waive its credit, and
    export_sources.py publishes attribution verbatim because that is what a
    licence obliges.
    """
    incomplete = sorted(
        f"{org['slug']} (endpoint={bool(org['endpoint'])}, attribution={bool(org['attribution'])})"
        for org in orgs
        if org["load"] == "ship" and not (org["endpoint"] and org["attribution"])
    )
    assert incomplete == [], f"ship rows missing an endpoint or an attribution: {incomplete}"


def test_a_row_with_no_geometry_to_fetch_claims_no_endpoint(orgs):
    """`none` is 25 advocacy organizations and 13 route-only trails.

    A route with an endpoint is a contradiction: the Hayduke has no maintainer
    and no dataset, and a URL on that row would be somebody's trip report
    wearing a source's clothes.
    """
    contradictory = sorted(o["slug"] for o in orgs if o["load"] == "none" and o["endpoint"])
    assert contradictory == [], f"rows with nothing to load but an endpoint anyway: {contradictory}"


def test_every_licence_basis_is_one_of_the_four_sources_json_already_uses(orgs):
    """The catalogue must not invent a fifth way of saying where a licence came from.

    sources.json uses maintainer_authorisation, stated_by_org and unresolved
    today; public_domain is the fourth this catalogue adds, and 'unstated'
    replaces 'unresolved' because it says which of the two it is - nobody asked,
    rather than somebody asked and got no answer.
    """
    used = {o["licence_basis"] for o in orgs if o["licence_basis"] is not None}
    unknown = sorted(used - LICENCE_BASES)
    assert unknown == [], f"licence bases nothing defines: {unknown}"


def test_a_refused_row_says_which_terms_refused_it(orgs):
    """Six organizations state a real restriction, and assume-open must not reach them.

    A refusal with no stated licence is indistinguishable from a row nobody got
    round to reading, which is the distinction the whole catalogue exists to
    keep - and the one the maintainer's assume-open instruction turns on.
    """
    unexplained = sorted(o["slug"] for o in orgs if o["load"] == "refuse" and o["licence_basis"] != "stated_by_org")
    assert unexplained == [], f"refused without the organization having stated anything: {unexplained}"


def test_every_row_says_why_in_a_sentence_somebody_else_can_read(orgs):
    """`why` is the column a reviewer reviews. A blank one makes the row unreviewable."""
    thin = sorted(o["slug"] for o in orgs if len((o.get("why") or "").strip()) < 40)
    assert thin == [], f"rows whose reasoning is too thin to review: {thin}"


def test_confidence_is_recorded_wherever_an_endpoint_is_claimed(orgs):
    """`inferred` means the URL was never opened, and the research says so outright.

    Losing that distinction would turn 'well-supported guess' into 'tested
    endpoint' silently, which is the failure CLAUDE.md's evidence grades exist
    to prevent.
    """
    assert {"verified", "inferred"} >= {o["confidence"] for o in orgs if o["endpoint"]}
    unmarked = sorted(o["slug"] for o in orgs if o["endpoint"] and not o.get("confidence"))
    assert unmarked == [], f"endpoints with no confidence recorded: {unmarked}"


def test_nothing_in_the_catalogue_is_registered_as_shipping_by_this_file_alone(orgs):
    """The catalogue proposes; a sources.json entry in a merged pull request registers.

    This is SOURCE_REGISTRY.md's rule restated as a test: the file carries a
    `ship` verdict and carries no mechanism for acting on it, so a row cannot
    reach a hiker by being edited here.
    """
    assert not any("reaches_hikers" in org for org in orgs), (
        "trail_orgs.json must not carry reaches_hikers - that field belongs to sources.json, where a merge is what sets it"
    )
