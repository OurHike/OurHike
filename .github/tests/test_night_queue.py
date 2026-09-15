"""The night lane's gate, held where it can be re-checked without a token (#1463).

scripts/night_queue.py decides which open issues an unattended session may pick
up. That decision runs while nobody is watching, so the cost of it being wrong
is asymmetric in the direction this repository already cares about: letting a
`client` issue through means a change a hiker can see lands without anybody
looking at it on a phone, and dropping a server-side one means work quietly
does not happen and looks exactly like work that was already done.

Deliberately fixture-driven rather than pointed at the live backlog. The rule
is a pure function of labels (that is why it is a separate file from the fetch
in scripts/nightshift.sh), and a test that asked GitHub would go red whenever
somebody relabelled an issue - which is the opposite of a regression signal.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import night_queue  # noqa: E402


def issue(number=1, labels=(), title="t", updated_at="2026-01-01T00:00:00Z", **extra):
    return {"number": number, "title": title, "labels": list(labels), "updated_at": updated_at, **extra}


def eligible(**kwargs):
    ok, _ = night_queue.verdict(issue(**kwargs))
    return ok


def reason(**kwargs):
    _, why = night_queue.verdict(issue(**kwargs))
    return why


class TestTheGateLetsServerSideWorkThrough:
    @pytest.mark.parametrize("area", sorted(night_queue.AREA))
    def test_every_area_label_alone_is_enough(self, area):
        assert eligible(labels=[area]), f"{area} should route to the night lane on its own"

    def test_a_qualifier_alongside_an_area_label_does_not_block_it(self):
        # v2/v3/research/enhancement are qualifiers, not areas. An issue that
        # is `pipeline` AND `research` is still pipeline work.
        assert eligible(labels=["pipeline", "research", "v2"])


class TestTheGateHoldsBackTheMaintainersLane:
    def test_client_is_the_other_lane(self):
        assert not eligible(labels=["client", "pipeline"])
        assert "maintainer's lane" in reason(labels=["client", "pipeline"])

    def test_client_wins_even_against_every_area_label(self):
        assert not eligible(labels=["client", *night_queue.AREA])

    def test_the_hold_label_is_an_unconditional_veto(self):
        assert not eligible(labels=["night-shift-hold", "pipeline", "ops"])
        assert "veto" in reason(labels=["night-shift-hold", "pipeline"])

    def test_the_hold_label_outranks_every_other_reason(self):
        # The veto is the maintainer's sentence, so it is the one printed even
        # when three other disqualifiers would also have caught the issue.
        assert "veto" in reason(labels=["night-shift-hold", "client", "blocked-external"])

    @pytest.mark.parametrize("label", ["blocked-external", "needs-field-testing"])
    def test_waiting_on_somebody_is_not_waiting_on_work(self, label):
        assert not eligible(labels=[label, "pipeline"])


class TestTheGateRefusesWhatItCannotRoute:
    def test_an_unlabeled_issue_is_invisible_to_the_rule(self):
        # The defect #1463 exists for: 32 of 112 open issues were here.
        assert not eligible(labels=[])
        assert "unlabeled" in reason(labels=[])

    def test_qualifiers_alone_are_not_an_area(self):
        assert not eligible(labels=["v2"])
        assert "no area label" in reason(labels=["v2"])
        assert "v2" in reason(labels=["v2"]), "the reason names what the issue does carry"


class TestWorkAlreadyInFlightIsNotTakenTwice:
    def test_an_open_pull_request_closing_it_is_a_claim(self):
        assert not eligible(labels=["pipeline"], has_open_pr=True)
        assert "in flight" in reason(labels=["pipeline"], has_open_pr=True)

    def test_a_claim_comment_is_a_claim(self):
        assert not eligible(labels=["pipeline"], claimed=True)

    def test_in_flight_is_checked_before_the_labels_are(self):
        # A branch that is already building a `client` issue should read as in
        # flight rather than as the other lane - the second sentence would send
        # a session looking for different work when the answer is "somebody is
        # already on it".
        assert "in flight" in reason(labels=["client"], has_open_pr=True)


class TestTheRanking:
    def test_a_red_check_comes_before_everything(self):
        order = night_queue.queue(
            [
                issue(number=2, labels=["pipeline"], updated_at="2020-01-01T00:00:00Z"),
                issue(number=1, labels=["deployment-health"], updated_at="2030-01-01T00:00:00Z"),
            ]
        )
        assert [i["number"] for i in order] == [1, 2], "deployment-health is open only while a check is red"

    def test_a_dropped_handoff_comes_before_ordinary_work(self):
        order = night_queue.queue(
            [
                issue(number=2, labels=["pipeline"], updated_at="2020-01-01T00:00:00Z"),
                issue(number=1, labels=["release-followup"], updated_at="2030-01-01T00:00:00Z"),
            ]
        )
        assert [i["number"] for i in order] == [1, 2]

    def test_within_a_tier_the_least_recently_touched_goes_first(self):
        order = night_queue.queue(
            [
                issue(number=1, labels=["ops"], updated_at="2026-09-01T00:00:00Z"),
                issue(number=2, labels=["ops"], updated_at="2026-01-01T00:00:00Z"),
            ]
        )
        assert [i["number"] for i in order] == [2, 1]

    def test_the_order_is_total_so_two_nights_agree(self):
        # Same timestamp, same tier: the issue number breaks the tie rather
        # than the order the API happened to return them in. Two sessions
        # reading the same backlog must pick the same issue.
        same = [issue(number=n, labels=["ops"], updated_at="2026-01-01T00:00:00Z") for n in (9, 3, 7)]
        assert [i["number"] for i in night_queue.queue(same)] == [3, 7, 9]
        assert [i["number"] for i in night_queue.queue(list(reversed(same)))] == [3, 7, 9]


class TestLabelShapes:
    def test_rest_objects_and_graphql_strings_both_read(self):
        # scripts/nightshift.sh fetches REST (labels are objects with a name);
        # the GitHub MCP tools hand back bare strings. Both reach this rule.
        assert night_queue._labels({"labels": [{"name": "pipeline"}]}) == {"pipeline"}
        assert night_queue._labels({"labels": ["pipeline"]}) == {"pipeline"}

    def test_a_missing_or_null_label_list_is_no_labels_rather_than_a_crash(self):
        assert night_queue._labels({}) == set()
        assert night_queue._labels({"labels": None}) == set()


class TestTheCensus:
    def test_the_buckets_count_what_they_say(self):
        counts = night_queue.census(
            [
                issue(number=1, labels=["client"]),
                issue(number=2, labels=["client", "pipeline"]),
                issue(number=3, labels=["pipeline"]),
                issue(number=4, labels=[]),
                issue(number=5, labels=["blocked-external", "data"]),
                issue(number=6, labels=["deployment-health"]),
            ]
        )
        assert counts["open issues"] == 6
        assert counts["carry `client`"] == 2
        assert counts["server-side only"] == 2, "pipeline and data, minus the two carrying client"
        assert counts["no label at all"] == 1
        assert counts["blocked-external"] == 1
        assert counts["deployment-health"] == 1

    def test_eligible_tonight_agrees_with_the_queue(self):
        issues = [
            issue(number=1, labels=["pipeline"]),
            issue(number=2, labels=["client"]),
            issue(number=3, labels=[]),
        ]
        assert night_queue.census(issues)["eligible tonight"] == len(night_queue.queue(issues))


def test_a_title_is_never_printed_as_a_bare_number():
    """CLAUDE.md, "Name an issue or PR, don't just number it"."""
    rendered = night_queue._title({"number": 42, "title": "The thing that is wrong"})
    assert "#42" in rendered
    assert "The thing that is wrong" in rendered
