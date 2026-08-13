"""Tests that the privacy policy still describes the app (#104).

`site/Privacy/index.html` is a legal document, and the one way it goes wrong is
by staying still while the code moves. Both stores require it, and a policy
that names a sign-in method the build does not offer, or omits a third party
the app talks to, is worse than a missing one: it is a specific promise nobody
kept.

That already happened on all three counts the tests below now hold, and none of
it was anybody being careless - each was true when written:

  - it offered **Apple** sign-in, which is not in the shipped provider set and
    which #92 records as never having been exercised at all;
  - it said nothing about **notifications**, while `lib/push.ts` carries a hard
    guarantee worth telling a hiker about;
  - it named Cloudflare and "elevation-tile sources" for map data, and did not
    name **OpenFreeMap**, which serves the default background - and which tile
    you request says roughly where you are looking.

WHY THIS IS A TEST AND NOT A REVIEW HABIT. The precedent is
`test_status_page.py` next door: a page that silently kept its placeholder
would report itself unconfigured forever while looking deployed. Same shape
here. The policy is prose, so nothing compiles it and nothing else in the repo
would ever notice it drifting - and the reader it drifts on is a hiker deciding
whether to trust the app with their location.

These assert against the CLIENT'S OWN SOURCE rather than a list kept here, for
the reason `verify_release.py` gives about parsing `config.ts`: a hand-kept
copy is a second home for the contract, and the whole failure being guarded
against is two homes disagreeing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY = REPO_ROOT / "site" / "Privacy" / "index.html"
CLIENT_LIB = REPO_ROOT / "client" / "src" / "lib"
CLIENT_MAP = REPO_ROOT / "client" / "src" / "map"

# Hosts the client fetches map data from at runtime. Read out of the modules
# that declare them rather than listed here - see the module docstring.
TILE_SOURCE_FILES = ("liveTopo.ts", "terrain.ts")


@pytest.fixture(scope="module")
def policy() -> str:
    return POLICY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def enabled_providers() -> set[str]:
    """The sign-in providers a build ships when nothing overrides them.

    `VITE_AUTH_PROVIDERS` can widen this per build, but the default is what
    every deployed build has unless somebody set it - so it is what the policy
    has to describe.
    """
    source = (CLIENT_LIB / "supabase.ts").read_text(encoding="utf-8")
    match = re.search(r"CONFIGURED_PROVIDERS\.trim\(\) === ''\s*\?\s*'([^']+)'", source)
    if match is None:
        raise AssertionError(
            "could not read the default provider set out of client/src/lib/supabase.ts. "
            "It has been restructured, and this test must be updated rather than left "
            "asserting nothing."
        )
    return {name.strip() for name in match.group(1).split(",") if name.strip()}


@pytest.fixture(scope="module")
def tile_hosts() -> set[str]:
    """Every third-party host the map fetches tiles from."""
    hosts = set()
    for name in TILE_SOURCE_FILES:
        source = (CLIENT_MAP / name).read_text(encoding="utf-8")
        for url in re.findall(r"^\s*(?:export const \w+ =\s*)?'(https://[^']+)'", source, re.MULTILINE):
            hosts.add(re.sub(r"^https://", "", url).split("/")[0])
    if not hosts:
        raise AssertionError(
            "found no tile hosts in client/src/map/. Either they moved or the pattern "
            "stopped matching, and a test that checks nothing is worse than no test."
        )
    return hosts


def test_the_policy_is_where_the_site_build_will_publish_it():
    assert POLICY.is_file()


def test_it_does_not_offer_a_sign_in_the_build_does_not_have(policy: str, enabled_providers: set[str]):
    """Apple was named here for months and is not in the shipped set. A policy
    describing a route that does not exist is a promise to a reader who has no
    way to check it."""
    if "apple" not in enabled_providers:
        assert not re.search(r"\bApple\b", policy), "the policy mentions Apple sign-in and `google,email` is the shipped default"


def test_it_names_every_provider_that_is_shipped(policy: str, enabled_providers: set[str]):
    """The other direction, which matters just as much: a provider that ships
    unmentioned is personal data collected without being disclosed."""
    for provider in enabled_providers:
        if provider == "email":
            assert "email address" in policy
        else:
            assert re.search(rf"\b{provider}\b", policy, re.IGNORECASE), provider


def test_it_names_every_host_the_map_fetches_tiles_from(policy: str, tile_hosts: set[str]):
    """Which tile you ask for says roughly where you are looking, so the list
    of who receives that is the sentence a privacy-minded reader leans on
    hardest. `openfreemap.org` served the default background for ten days
    without appearing here."""
    for host in tile_hosts:
        # The registrable name rather than the full host, so `tiles.` moving to
        # `cdn.` is not a false failure - what a reader needs is WHO, not which
        # subdomain.
        name = ".".join(host.split(".")[-2:])
        assert name in policy, f"{host} serves map data and the policy does not name it"


def test_it_states_the_one_notification_rule(policy: str):
    """`lib/push.ts` is the single place allowed to send one, and
    `lib/push.test.ts` scans the source tree to keep that true. A guarantee
    that strong is worth a sentence, and #104 asks for it by name."""
    assert re.search(r"off-trail alert", policy, re.IGNORECASE)
    assert "notification" in policy.lower()


def test_it_still_says_location_stays_on_the_device(policy: str):
    """The claim a hiker is most likely to be deciding on, and the one this
    app can actually make."""
    assert "on your device only" in policy


def test_it_carries_a_date(policy: str):
    """A policy with no date cannot be reasoned about - "we'll update the date
    at the top" is a promise this file makes about itself."""
    assert re.search(r"Last updated \w+ \d{1,2}, \d{4}", policy)
