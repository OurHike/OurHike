"""The usage report's mask (#1902, app/core/analytics_report.py).

"A mask at runtime though. Dont mess with the data" (the maintainer, poll
2026-10-27): the stored figures stay exact, and every report masks the same
way when it is built. The test that matters most is the last one here - a
masked figure is not merely hidden by the page, it is not in the file at all.
"""

import importlib.util
import re
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy.dialects.postgresql import insert

from app.core import analytics_quality as quality
from app.core import analytics_storage
from app.core.analytics_report import K_FLOOR, build_report_data, mask_cells
from app.models.analytics import AnalyticsEvent, AnalyticsMonth, AnalyticsMonthly, AnalyticsUser, MonthStatus

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "usage_report.py"
OCTOBER = date(2026, 10, 1)


@pytest.fixture(scope="module")
def report_script():
    spec = importlib.util.spec_from_file_location("usage_report", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_clubs_plans_under_the_floor_are_masked_with_their_miles_though_the_club_has_enough_phones():
    """A club cell counts no phones per kind of event, so `FOLLOWERS` cannot
    reach its plans: "1 plan, 12.5 miles" was one hiker's (#1903's second review)."""
    masked, _ = mask_cells({"2026-10|GATC|*": {"devices_active": 30, "plans_made": 1.0, "plan_miles": 12.5, "map_views": 40}})

    assert masked["2026-10|GATC|*"] == {"devices_active": 30, "plans_made": None, "plan_miles": None, "map_views": 40}


def test_one_session_length_under_the_floor_masks_all_four_since_they_add_up_to_the_visits():
    lengths = {"sessions_under_1m": 10, "sessions_m1_to_5": 9, "sessions_m5_to_20": 5, "sessions_over_20m": 2}
    masked, _ = mask_cells({"2026-10|*|web": {"devices_active": 26, "sessions": 26, **lengths}})

    assert all(masked["2026-10|*|web"][part] is None for part in lengths)
    assert masked["2026-10|*|web"]["sessions"] == 26


def test_a_cell_describing_fewer_than_the_floor_is_masked_whole():
    masked, whole = mask_cells({"2026-10|GMC|*": {"devices_active": K_FLOOR - 1, "plans_made": 3.5, "map_views": 40}})

    assert masked["2026-10|GMC|*"] == {"devices_active": None, "plans_made": None, "map_views": None}
    assert whole == {"2026-10|GMC|*"}


def test_a_cell_at_the_floor_is_shown():
    masked, whole = mask_cells({"2026-10|*|*": {"devices_active": K_FLOOR, "map_views": 40}})

    assert masked["2026-10|*|*"]["map_views"] == 40 and not whole


def test_an_event_count_under_the_floor_is_masked_in_a_shown_cell():
    """Four plans were made by four people at most, whatever the cell's size."""
    masked, _ = mask_cells({"2026-10|*|*": {"devices_active": K_FLOOR, "plans_made": 4}})

    assert masked["2026-10|*|*"]["plans_made"] is None


def test_a_small_count_of_hikers_who_said_yes_is_masked_inside_a_shown_cell():
    masked, _ = mask_cells({"2026-10|*|*": {"devices_active": 900, "hikers_active": 12, "map_views": 3000}})

    assert masked["2026-10|*|*"]["hikers_active"] is None
    assert masked["2026-10|*|*"]["map_views"] == 3000


def test_a_small_count_of_phones_inside_a_shown_cell_is_masked():
    masked, _ = mask_cells({"2026-10|*|*": {"devices_active": 900, "devices_plan_completed": 9, "devices_plan_made": 300}})

    assert masked["2026-10|*|*"]["devices_plan_completed"] is None
    assert masked["2026-10|*|*"]["devices_plan_made"] == 300


def test_a_count_whose_complement_is_small_is_masked_too():
    """Of 900 phones, "880 viewed the map" says 20 did not."""
    masked, _ = mask_cells(
        {"2026-10|*|*": {"devices_active": 900, "devices_map_view": 880, "hikers_active": 40, "plan_hikers": 31}}
    )

    assert masked["2026-10|*|*"]["devices_map_view"] is None
    assert masked["2026-10|*|*"]["plan_hikers"] is None, "40 linked hikers, 31 planned: 9 did not"
    assert masked["2026-10|*|*"]["hikers_active"] == 40


def test_one_masked_part_of_the_growth_split_masks_all_three():
    """New + returning + back-again = active, so two shown parts give the third."""
    cell = {"devices_active": 400, "devices_new": 12, "devices_returning": 300, "devices_back": 88}

    masked, _ = mask_cells({"2026-10|*|*": cell})

    assert [masked["2026-10|*|*"][part] for part in ("devices_new", "devices_returning", "devices_back")] == [
        None,
        None,
        None,
    ]
    assert masked["2026-10|*|*"]["devices_active"] == 400


def test_a_count_of_nobody_stays_zero():
    masked, _ = mask_cells({"2026-10|*|*": {"devices_active": 900, "plan_hikers": 0}})

    assert masked["2026-10|*|*"]["plan_hikers"] == 0


def test_one_hidden_club_takes_the_next_smallest_with_it():
    """Otherwise the hidden club could be had by subtracting the others from the total."""
    cells = {
        "2026-10|*|*": {"devices_active": 500},
        "2026-10|NYNJTC|*": {"devices_active": 300},
        "2026-10|PATC|*": {"devices_active": 60},
        "2026-10|GMC|*": {"devices_active": 9},
    }

    _, whole = mask_cells(cells)

    assert whole == {"2026-10|GMC|*", "2026-10|PATC|*"}


def test_two_hidden_clubs_need_no_third():
    cells = {
        "2026-10|*|*": {"devices_active": 500},
        "2026-10|NYNJTC|*": {"devices_active": 300},
        "2026-10|GMC|*": {"devices_active": 9},
        "2026-10|RATC|*": {"devices_active": 4},
    }

    _, whole = mask_cells(cells)

    assert whole == {"2026-10|GMC|*", "2026-10|RATC|*"}


def test_one_hidden_platform_takes_the_next_smallest_with_it():
    cells = {
        "2026-10|*|*": {"devices_active": 300},
        "2026-10|*|ios": {"devices_active": 200},
        "2026-10|*|android": {"devices_active": 90},
        "2026-10|*|web": {"devices_active": 10},
    }

    _, whole = mask_cells(cells)

    assert whole == {"2026-10|*|web", "2026-10|*|android"}


def test_a_platform_of_no_devices_is_shown_as_its_zeros_and_hides_nothing_beside_it():
    """An app with no web users used to lose its Android figures too: the
    empty web cell was masked, and rule 3 hid the next-smallest with it."""
    cells = {
        "2026-10|*|*": {"devices_active": 300, "sessions": 900},
        "2026-10|*|ios": {"devices_active": 200, "sessions": 600},
        "2026-10|*|android": {"devices_active": 100, "sessions": 300},
        "2026-10|*|web": {"devices_active": 0, "sessions": 0},
    }

    masked, whole = mask_cells(cells)

    assert whole == set()
    assert masked["2026-10|*|web"] == {"devices_active": 0, "sessions": 0}
    assert masked["2026-10|*|android"]["sessions"] == 300


def test_a_cell_of_no_devices_masks_anything_in_it_that_is_not_zero():
    """Plans with no phone counted are phones nobody counted - a first row of
    the month still on a ridge - and a zero beside them cannot cover them."""
    masked, _ = mask_cells({"2026-10|GMC|*": {"devices_active": 0, "plans_made": 2.0, "map_views": 0}})

    assert masked["2026-10|GMC|*"] == {"devices_active": 0, "plans_made": None, "map_views": 0}


@pytest.mark.parametrize(
    "people, events",
    [
        ("devices_new", ["installs"]),
        ("devices_plan_made", ["plans_made", "plan_miles"]),
        ("devices_plan_completed", ["plans_completed", "completed_miles"]),
        ("devices_login", ["logins"]),
        ("devices_map_view", ["map_views"]),
        ("hikers_active", ["events_identified"]),
    ],
)
def test_events_are_masked_with_the_count_of_people_who_made_them(people, events):
    """Reproduced for installs: a month's installs is its new phones near
    enough, so it printed the number devices_new was masked to hide."""
    cell = {"devices_active": 900, people: 12, **{event: 15 for event in events}}

    masked, _ = mask_cells({"2026-10|*|*": cell})

    assert [masked["2026-10|*|*"][event] for event in events] == [None] * len(events)


def test_hidden_platforms_are_hidden_together_until_they_hold_the_floor():
    """Two hidden platforms of 10 and 5 came back as a 15 by subtraction."""
    cells = {
        "2026-10|*|*": {"devices_active": 300},
        "2026-10|*|ios": {"devices_active": 285},
        "2026-10|*|android": {"devices_active": 10},
        "2026-10|*|web": {"devices_active": 5},
    }

    _, whole = mask_cells(cells)

    assert whole == {"2026-10|*|ios", "2026-10|*|android", "2026-10|*|web"}


def test_a_metric_masked_inside_one_platform_is_masked_in_the_next_smallest_too():
    """Platforms add up to the whole app exactly, so iOS's masked 10 would be
    the total less Android and the web."""
    cells = {
        "2026-10|*|*": {"devices_active": 600, "devices_plan_completed": 66, "plans_completed": 70},
        "2026-10|*|ios": {"devices_active": 300, "devices_plan_completed": 10, "plans_completed": 11},
        "2026-10|*|android": {"devices_active": 200, "devices_plan_completed": 30, "plans_completed": 31},
        "2026-10|*|web": {"devices_active": 100, "devices_plan_completed": 26, "plans_completed": 28},
    }

    masked, whole = mask_cells(cells)

    assert not whole
    assert masked["2026-10|*|ios"]["devices_plan_completed"] is None
    assert masked["2026-10|*|web"]["devices_plan_completed"] is None, "the next-smallest platform"
    assert masked["2026-10|*|web"]["plans_completed"] is None, "and the events that go with it"
    assert masked["2026-10|*|android"]["devices_plan_completed"] == 30


def test_lost_since_last_month_is_worked_out_and_masked_by_the_server():
    cells = {
        "2026-09|*|*": {"devices_active": 400},
        "2026-10|*|*": {"devices_active": 400, "devices_new": 50, "devices_returning": 300, "devices_back": 50},
    }

    masked, _ = mask_cells(cells)

    assert masked["2026-10|*|*"]["devices_lost"] == 100


def test_returning_phones_are_masked_when_last_month_less_them_is_under_the_floor():
    """390 of September's 400 back in October says 10 were lost: the page
    used to print that subtraction, and both of its inputs."""
    cells = {
        "2026-09|*|*": {"devices_active": 400},
        "2026-10|*|*": {"devices_active": 450, "devices_new": 30, "devices_returning": 390, "devices_back": 30},
    }

    masked, _ = mask_cells(cells)

    october = masked["2026-10|*|*"]
    assert october["devices_lost"] is None
    assert [october[part] for part in ("devices_new", "devices_returning", "devices_back")] == [None, None, None]
    assert october["devices_active"] == 450


def test_a_support_level_chosen_by_fewer_than_the_floor_is_masked_and_the_rest_shown():
    masked, _ = mask_cells(
        {"2026-10|*|*": {"devices_active": 900, "support_chosen_0": 300, "support_chosen_6000": 4, "support_chosen_1200": 0}}
    )

    assert masked["2026-10|*|*"]["support_chosen_6000"] is None
    assert masked["2026-10|*|*"]["support_chosen_0"] == 300
    assert masked["2026-10|*|*"]["support_chosen_1200"] == 0, "a count of nobody describes nobody"


def test_the_report_lists_every_support_level_any_month_holds(db_session):
    db_session.add(AnalyticsMonth(month=OCTOBER, status=MonthStatus.provisional, definition_version=2))
    for metric, value in (("devices_active", 400), ("support_chosen_0", 30), ("support_chosen_12000", 3)):
        db_session.add(AnalyticsMonthly(month=OCTOBER, metric=metric, club="*", platform="*", value=value))
    db_session.commit()

    data = build_report_data(db_session, environment="Test")

    assert data["support_levels"] == [0, 12000]
    assert data["cells"]["2026-10|*|*"]["support_chosen_12000"] is None


def _month_with_a_small_club(db_session):
    db_session.add(AnalyticsMonth(month=OCTOBER, status=MonthStatus.provisional, definition_version=1))
    for club, devices, miles in (("*", 400, 5000.0), ("NYNJTC", 300, 4300.0), ("PATC", 80, 650.5), ("GMC", 9, 271.75)):
        db_session.add(AnalyticsMonthly(month=OCTOBER, metric="devices_active", club=club, platform="*", value=devices))
        db_session.add(AnalyticsMonthly(month=OCTOBER, metric="plan_miles", club=club, platform="*", value=miles))
    db_session.commit()


def test_the_report_data_carries_no_figure_for_a_masked_cell(db_session):
    _month_with_a_small_club(db_session)

    data = build_report_data(db_session, environment="Test")

    assert data["cells"]["2026-10|GMC|*"] == {"devices_active": None, "plan_miles": None}
    assert data["cells"]["2026-10|*|*"]["plan_miles"] == 5000.0


def test_a_masked_figure_is_not_anywhere_in_the_written_file(db_session, report_script):
    """Not hidden by the page's script: absent. A copy forwarded to a club
    cannot be read past the mask with view-source."""
    _month_with_a_small_club(db_session)

    html = report_script.render(build_report_data(db_session, environment="Test"))

    assert "271.75" not in html
    assert "650.5" not in html, "PATC is hidden with GMC, or GMC is total minus the others"
    assert "4300" in html, "the shown figures are in the file, which is what makes the test above mean something"


def test_cohorts_hide_a_cohort_smaller_than_the_floor(db_session):
    db_session.add(AnalyticsMonth(month=OCTOBER, status=MonthStatus.provisional, definition_version=1))
    for index in range(3):
        db_session.add(
            AnalyticsUser(
                user_key=f"{index:032d}",
                first_seen_on=date(2026, 9, 2),
                new_month=date(2026, 9, 1),
                last_seen_on=date(2026, 10, 2),
                first_platform="ios",
                last_platform="ios",
                active_months=[202609, 202610],
            )
        )
    db_session.commit()

    data = build_report_data(db_session, environment="Test")

    september = next(row for row in data["cohorts"] if row["cohort"] == "2026-09")
    assert september["size"] is None and september["retained"] == [None]
    assert data["users"]["hikers"] is None


def _cohort_of_30_with_28_back(db_session):
    db_session.add(AnalyticsMonth(month=OCTOBER, status=MonthStatus.provisional, definition_version=1))
    for index in range(30):
        db_session.add(
            AnalyticsUser(
                user_key=f"{index:032d}",
                first_seen_on=date(2026, 9, 2),
                new_month=date(2026, 9, 1),
                last_seen_on=date(2026, 10, 2),
                first_platform="ios",
                last_platform="ios",
                first_plan_on=date(2026, 9, 3) if index < 28 else None,
                active_months=[202609, 202610] if index < 28 else [202609],
            )
        )
    db_session.commit()


def test_a_cohorts_retention_is_masked_when_those_who_left_are_under_the_floor(db_session):
    """Of 30 hikers, "28 came back" says 2 did not."""
    _cohort_of_30_with_28_back(db_session)

    september = next(row for row in build_report_data(db_session, environment="Test")["cohorts"] if row["cohort"] == "2026-09")

    assert september["size"] == 30 and september["retained"] == [None]


def test_the_user_table_line_masks_a_count_whose_complement_is_under_the_floor(db_session):
    _cohort_of_30_with_28_back(db_session)

    users = build_report_data(db_session, environment="Test")["users"]

    assert users == {"hikers": 30, "ever_planned": None, "ever_completed": 0}


def test_the_quality_panel_publishes_no_band_edges_and_no_share_below_the_floor(db_session):
    """Reproduced: high / expected = 1 + 4/sqrt(E) gave the exact daily count
    back on 50 of 56 days. A share is published only where 25 or more were
    expected, and the band the page draws is fixed."""
    today = date(2026, 11, 20)
    rows = []
    for back in range(63, 0, -1):
        day = today - timedelta(days=back)
        for event, n in (("session", 40), ("hike_plan_made", 12)):
            for _ in range(n):
                rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "local_date": day,
                        "received_on": day,
                        "event": event,
                        "platform": "ios",
                        "week_first": False,
                        "month_first": False,
                        "ever_first": False,
                        "kind_month_first": False,
                        "month_returning": False,
                        "signed_in": False,
                        "has_fix": False,
                        "seal": "none",
                        "pageviews": 3 if event == "session" else None,
                        "session_length": "m1_to_5" if event == "session" else None,
                    }
                )
    db_session.execute(insert(AnalyticsEvent.__table__).values(rows))
    db_session.commit()

    panel = build_report_data(db_session, environment="Test", today=today)["quality"]

    assert panel["band"] == [0.5, 1.5]
    assert {key for points in panel["series"].values() for point in points for key in point} == {"day", "status", "share"}
    assert panel["series"]["sessions"][-1] == {"day": "2026-11-19", "status": "ok", "share": 1.0}
    assert panel["series"]["plans_made"][-1] == {"day": "2026-11-19", "status": "ok", "share": None}, "12 expected"


@pytest.mark.parametrize("months", [False, True], ids=["before-the-first-month", "with-months"])
def test_the_storage_strip_publishes_shares_and_whole_megabytes_never_a_row_count(db_session, monkeypatch, months):
    """Two reports a day apart would otherwise give the rows stored between them."""
    monkeypatch.setattr(analytics_storage.settings, "analytics_storage_ceiling_mb", 250)
    monkeypatch.setattr(analytics_storage.settings, "database_quota_mb", 500)
    monkeypatch.setattr(analytics_storage, "rows_held", lambda db: 123_457)
    monkeypatch.setattr(analytics_storage, "usage_tables_bytes", lambda db: int(47.6 * 1024 * 1024))
    monkeypatch.setattr(analytics_storage, "database_bytes", lambda db: int(130.2 * 1024 * 1024))
    if months:
        db_session.add(AnalyticsMonth(month=OCTOBER, status=MonthStatus.closed, definition_version=1))
        db_session.commit()

    storage = build_report_data(db_session, environment="Test")["quality"]["storage"]

    assert storage == {
        "rows": {"share": 0.18, "status": "ok"},
        "usage": {"mb": 48, "of_mb": 250, "share": 0.19, "status": "ok"},
        "database": {"mb": 130, "of_mb": 500, "share": 0.26, "status": "ok"},
        "warn_share": 0.8,
    }


def test_the_storage_strip_is_judged_by_the_nightly_checks_line_not_by_the_page(db_session, monkeypatch):
    """A share that rounds to 0.80 is not a warning unless the check would raise one."""
    monkeypatch.setattr(analytics_storage.settings, "analytics_storage_ceiling_mb", 100)
    monkeypatch.setattr(analytics_storage.settings, "database_quota_mb", 100)
    monkeypatch.setattr(analytics_storage, "rows_held", lambda db: 0)
    monkeypatch.setattr(analytics_storage, "usage_tables_bytes", lambda db: int(79.6 * 1024 * 1024))
    monkeypatch.setattr(analytics_storage, "database_bytes", lambda db: 80 * 1024 * 1024)

    storage = build_report_data(db_session, environment="Test")["quality"]["storage"]

    assert (storage["usage"]["share"], storage["usage"]["status"]) == (0.8, "ok")
    assert (storage["database"]["share"], storage["database"]["status"]) == (0.8, "warn")


def test_every_check_the_nightly_job_names_has_a_label_in_the_page(report_script):
    """A finding shown as `rows_unsealed_no_key` is a finding nobody reads."""
    template = report_script.TEMPLATE.read_text(encoding="utf-8")
    block = re.search(r"var CHECK_NAMES = \{(.*?)\};", template, re.DOTALL)
    names = re.search(r"var QUALITY_NAMES = \{(.*?)\};", template, re.DOTALL)
    assert block is not None and names is not None, "CHECK_NAMES or QUALITY_NAMES is not where this test reads it"

    labelled = set(re.findall(r"(\w+):", block.group(1)))
    metrics = set(re.findall(r"(\w+):", names.group(1)))

    assert set(quality.NAMED_CHECKS) - labelled == set()
    assert set(quality.VOLUME_METRICS) | set(quality.PER_SESSION) | set(quality.PLATFORM_METRICS) <= metrics


def test_the_page_draws_the_servers_figures_rather_than_working_out_its_own(report_script):
    """Lost phones and the quality band both used to be computed in the page,
    from figures the file carried - which is how the masks were got round."""
    template = report_script.TEMPLATE.read_text(encoding="utf-8")

    assert "'devices_lost'" in template and "before - returning" not in template
    assert "q.band" in template and re.search(r"\bp\.(low|high)\b", template) is None


def test_an_empty_database_builds_an_empty_report(db_session, report_script):
    html = report_script.render(build_report_data(db_session, environment="Test"))

    assert '"months":[]' in html


def test_the_page_template_holds_its_data_slot_exactly_once(report_script):
    assert report_script.TEMPLATE.read_text(encoding="utf-8").count(report_script.PLACEHOLDER) == 1


def test_no_value_can_close_the_data_block_early(report_script):
    html = report_script.render({"months": [], "note": "</script><script>alert(1)</script>"})

    assert "</script><script>alert" not in html


def test_the_report_refuses_to_be_written_into_the_repository(report_script, tmp_path):
    inside = Path(__file__).resolve().parents[2] / "usage-report.html"

    assert report_script.main(["--out", str(inside)]) == 2
    assert not inside.exists()
