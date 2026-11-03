"""The backend's copy of the challenge publishers, held to the pipeline's.

app/core/trail_challenge.py's PUBLISHER_DOMAINS repeats
pipeline/reference/challenges/publishers.json's `org` -> `domain`, because the
backend never reads the pipeline's files. The two disagreeing would let a
domain the pipeline publishes as the ATC be one the backend does not hold the
`atc` slug for, or the reverse. Read as text, test_client_report_contract.py's
way, so nothing here imports the pipeline.
"""

import json
from pathlib import Path

from app.core.trail_challenge import PUBLISHER_DOMAINS, may_publish_as

PUBLISHERS = Path(__file__).resolve().parents[2] / "pipeline" / "reference" / "challenges" / "publishers.json"


def test_the_backend_holds_every_publisher_the_pipeline_names_at_the_same_domain():
    rows = json.loads(PUBLISHERS.read_text(encoding="utf-8"))["publishers"]

    assert {row["org"]: row["domain"].strip().lower() for row in rows} == PUBLISHER_DOMAINS


def test_a_publisher_org_is_the_proved_domains_whatever_the_clubs_slug():
    assert may_publish_as("atc", slug="appalachian-trail-conservancy", domain="appalachiantrail.org")
    assert may_publish_as("atc", slug="atc", domain="AppalachianTrail.org")
    # A squatter on the slug, with a domain of their own.
    assert not may_publish_as("atc", slug="atc", domain="evil.example")
    assert not may_publish_as("atc", slug="evil", domain="evil.example")
    # An ordinary org publishes as itself.
    assert may_publish_as("ramapo-trail-conference", slug="ramapo-trail-conference", domain="ramapotrails.org")
