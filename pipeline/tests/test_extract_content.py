"""extract/_content.py, decision 54 wave 3's content readers (section C), against mocked servers.

Each reader is asked for its rows directly, or run through the monthly lane into a `file://` raw store under
tmp_path where what lands is the question. requests_mock answers as each upstream did on section C's live reads of
2026-10-04; the bodies are invented and shaped like those answers. Nothing reaches the network: conftest.py's socket
guard stays on.

The cases are the ones a person, the zero and the lane turn on: a podcast feed's guest list, hosts' names and
e-mail addresses never reach a row; a row's own `person_fields` leave its episode notes out; NPS's content lists
read every row whatever page size the server keeps, refuse a repeated id, ask once more for a page cut short and
refuse it cut twice, and are withdrawn rather than read as empty without NPS_API_KEY; a guide's child pages are read by their parent; a hike type's terms ride the type's
monthly lane; and two templates on one wiki are two reads, not one dataset extracted twice.
"""

import json
import xml.etree.ElementTree as ElementTree
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import duckdb
import pytest

from extract import _content, _json_apis, _kinds, _notices
from extract._content import (
    PERSON_TAGS,
    MediawikiTemplatePages,
    NpsContent,
    PodcastEpisodes,
    SiteTerms,
    WordpressChildPages,
    mediawiki_template_pages,
    nps_content,
    podcast_episodes,
    site_terms,
    wordpress_child_pages,
)
from extract._contract import Unavailable, all_resources, discover
from extract._run import LEGS, lane_resources, make_pipeline, run_pipeline
from extract._warehouse import load_warehouse
from lib.freshness_state import Freshness

FEED = "https://feeds.example.org/show.rss"
NOTES_FEED = "https://feeds.example.org/notes.rss"
AUDIO = "https://nps.example.gov/api/v1/multimedia/audio"
ASSETS = "https://nps.example.gov/api/v1/multimedia/galleries/assets"
ALERTS = "https://nps.example.gov/api/v1/alerts"
SITE = "https://club.example.org"
WIKI = "https://club.example.org/clubwiki/api.php"


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A sources.json holding one entry per reader, in place of the real one."""
    path = tmp_path / "sources.json"
    sources = [
        {"key": "show_podcast", "kind": "podcast_feed", "url": FEED},
        {"key": "notes_podcast", "kind": "podcast_feed", "url": NOTES_FEED, "person_fields": ["description", "content_encoded"]},
        {"key": "not_a_feed", "kind": "published_notices", "url": FEED},
        {"key": "nps_audio", "url": AUDIO, "person_fields": ["transcript"]},
        {"key": "nps_assets", "url": ASSETS, "park_codes_from": "nps_alerts"},
        {"key": "nps_alerts", "url": ALERTS, "park_codes": {"semo": ["semo"], "lecl": ["lc-trust", "lcthf"]}},
        {"key": "guide_pages", "url": f"{SITE}/trails/"},
        {"key": "club_hikes", "url": f"{SITE}/wp-json/wp/v2/hikes"},
        {"key": "wiki_notices", "url": WIKI, "template": "Template:Announcement"},
        {"key": "wiki_trails", "url": WIKI, "template": "Template:Trail"},
    ]
    path.write_text(json.dumps({"sources": sources}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture(autouse=True)
def no_gap(monkeypatch):
    """No host is asked anything, so the readers' courtesy gaps are 0 here."""
    monkeypatch.setattr(_notices, "_pause", lambda seconds: None)
    monkeypatch.setattr(_json_apis, "POLITE_GAP_SECONDS", 0)
    monkeypatch.setattr(_json_apis, "_LAST_REQUEST_END", {})


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv(_json_apis.NPS_API_KEY_ENV, "test-key-not-real")


@pytest.fixture
def store(tmp_path):
    return {"bucket_url": (tmp_path / "raw-store").as_uri(), "pipelines_dir": str(tmp_path / "pipelines")}


def query(request) -> dict:
    return {name: values[0] for name, values in parse_qs(urlsplit(request.url).query).items()}


def feed(items: int = 2) -> str:
    """A podcast feed shaped like the live ones: every person tag section C met, an image by href, an enclosure."""
    body = "".join(
        f"<item><title>Fixture Episode {i}</title><guid>fixture-{i}</guid><pubDate>Mon, 2{i} Sep 2026 14:00:00 +0000</pubDate>"
        f"<description>Fixture notes {i}, call 555-0100.</description><content:encoded>Fixture notes {i}.</content:encoded>"
        f'<enclosure url="https://cdn.example.org/{i}.mp3" length="10{i}" type="audio/mpeg"/>'
        f'<itunes:image href="https://cdn.example.org/{i}.jpg"/><itunes:duration>00:3{i}:00</itunes:duration>'
        f"<itunes:author>Fixture Host, Fixture Guest</itunes:author><author>fixture.host@example.org</author>"
        f"<dc:creator>Fixture Host</dc:creator><podcast:person>Fixture Guest</podcast:person>"
        f"<itunes:owner><itunes:name>Fixture Owner</itunes:name><itunes:email>owner@example.org</itunes:email></itunes:owner>"
        f"</item>"
        for i in range(1, items + 1)
    )
    return (
        '<?xml version="1.0"?><rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:podcast="https://podcastindex.org/namespace/1.0">'
        f"<channel><title>Fixture Show</title><link>https://show.example.org/</link>{body}</channel></rss>"
    )


def episodes(key="show_podcast") -> PodcastEpisodes:
    return PodcastEpisodes(key=key, club="testclub", type="podcasts")


# --- podcasts ---------------------------------------------------------------------------------------------------


def test_a_podcast_feeds_guests_hosts_and_their_addresses_never_reach_a_row(registry, requests_mock):
    requests_mock.get(FEED, text=feed())

    rows = list(episodes().rows({}))

    values = json.dumps(rows)
    assert "Fixture Guest" not in values and "Fixture Host" not in values and "@example.org" not in values
    assert "Fixture Owner" not in values
    assert not {"itunes_author", "author", "ns_creator", "podcast_person", "itunes_owner"} & {
        name for row in rows for name in row
    }


def test_every_person_tag_is_left_out_by_its_namespaced_name():
    """The list is explicit (decision 59), so each tag the live feeds carried is named, namespace and all."""
    for tag in (
        "author",
        "{http://www.itunes.com/dtds/podcast-1.0.dtd}author",
        "{http://www.itunes.com/dtds/podcast-1.0.dtd}owner",
        "{http://purl.org/dc/elements/1.1/}creator",
        "{https://podcastindex.org/namespace/1.0}person",
        "{http://www.google.com/schemas/play-podcasts/1.0}author",
    ):
        assert tag in PERSON_TAGS, tag


def test_a_rows_person_fields_leave_its_episode_notes_out_and_the_rest_lands(registry, requests_mock):
    requests_mock.get(NOTES_FEED, text=feed())

    rows = list(episodes("notes_podcast").rows({}))

    assert all("description" not in row and "content_encoded" not in row for row in rows)
    assert "555-0100" not in json.dumps(rows)
    assert [row["guid"] for row in rows] == ["fixture-1", "fixture-2"]
    assert rows[0]["enclosure_url"] == "https://cdn.example.org/1.mp3" and rows[0]["itunes_duration"] == "00:31:00"


def test_without_person_fields_the_episode_notes_land_for_the_raw_store(registry, requests_mock):
    requests_mock.get(FEED, text=feed())

    rows = list(episodes().rows({}))

    assert rows[0]["description"].startswith("Fixture notes 1")


def test_an_itunes_image_lands_its_href_where_podcastfeed_landed_nothing(registry, requests_mock):
    requests_mock.get(FEED, text=feed())

    rows = list(episodes().rows({}))

    assert [row["itunes_image"] for row in rows] == ["https://cdn.example.org/1.jpg", "https://cdn.example.org/2.jpg"]


def test_a_feeds_item_count_is_its_proof_and_an_empty_channel_is_a_proven_zero(registry, requests_mock):
    requests_mock.get(FEED, text=feed(items=0))
    proofs = {}

    assert list(episodes().rows(proofs)) == []
    assert proofs == {"raw_testclub__show_podcast": 0}
    assert episodes().exact_proof


def test_a_304_to_the_feeds_own_validator_is_fresh(registry, requests_mock):
    requests_mock.get(FEED, status_code=304)

    verdict, marker = episodes().change_check({"etag": 'W/"abc"', "last_modified": None})

    assert verdict == Freshness.FRESH and marker == {"etag": 'W/"abc"', "last_modified": None}
    assert requests_mock.last_request.headers["If-None-Match"] == 'W/"abc"'


def test_a_feed_with_neither_validator_is_unknown_and_so_is_read(registry, requests_mock):
    requests_mock.get(FEED, text=feed())

    assert episodes().change_check(None) == (Freshness.UNKNOWN, None)


def test_an_answer_that_is_not_rss_raises_rather_than_reading_as_no_episodes(registry, requests_mock):
    requests_mock.get(FEED, text="<html><body>Fixture error page</body></html>")

    with pytest.raises(ValueError, match="not an RSS feed"):
        list(episodes().rows({}))


def test_podcast_episodes_refuses_a_row_that_is_not_a_podcast_feed(registry):
    with pytest.raises(ValueError, match="not a podcast_feed"):
        podcast_episodes("not_a_feed")


def test_a_podcast_lands_through_the_monthly_lane_with_no_person_column(registry, store, requests_mock):
    requests_mock.get(FEED, text=feed())

    report = run_pipeline("monthly", store["bucket_url"], resources=[episodes()], pipelines_dir=store["pipelines_dir"])

    assert report.outcome == "loaded" and report.rows["raw_testclub__show_podcast"] == 2
    con = duckdb.connect()
    counts = load_warehouse(con, make_pipeline("monthly", store["bucket_url"], store["pipelines_dir"]))
    assert counts["raw_testclub__show_podcast"] == 2
    columns = {row[0] for row in con.execute("describe raw.raw_testclub__show_podcast").fetchall()}
    assert {"guid", "title", "enclosure_url", "itunes_image", "show_title", "feed_items"} <= columns
    assert not {name for name in columns if "author" in name or "creator" in name or "person" in name or "owner" in name}


def test_every_registered_podcast_rides_the_monthly_lane_and_never_a_notices_leg():
    """The lead's condition (2026-10-04): a podcast's lane is its type's, and _run.job_of() takes only hourly resources."""
    readers = [r for r in all_resources(discover()) if isinstance(r, PodcastEpisodes)]
    assert readers, "the registry's podcast feeds are read by PodcastEpisodes"
    for resource in readers:
        assert resource.type == "podcasts" and resource.cadence == "monthly", resource.table
    assert lane_resources("hourly", readers) == []
    assert all(lane_resources(leg, readers) == [] for leg in LEGS), "no conditions or notices leg reads a podcast"
    assert lane_resources("monthly", readers) == readers


# --- NPS's content lists -----------------------------------------------------------------------------------------


class FakeList:
    """An NPS list: `total` as a string, pages of at most `cap` whatever `limit` asks, `start` an offset."""

    def __init__(self, requests_mock, url, rows, cap=500):
        self.rows, self.cap, self.asked = rows, cap, []
        requests_mock.get(url, json=self.answer)

    def answer(self, request, context):
        params = query(request)
        self.asked.append(params)
        start, limit = int(params["start"]), int(params["limit"])
        return {
            "total": str(len(self.rows)),
            "limit": str(limit),
            "start": str(start),
            "data": self.rows[start : start + min(limit, self.cap)],
        }


def clip(n):
    return {
        "id": f"00000000-0000-4000-8000-{n:012d}",
        "title": f"Fixture clip {n}",
        "transcript": f"Fixture life story {n}.",
        "relatedParks": [{"parkCode": "semo"}],
        "durationMs": 1000 * n,
    }


def test_an_nps_list_lands_every_row_when_the_server_serves_fewer_than_asked(registry, key, requests_mock):
    server = FakeList(requests_mock, AUDIO, [clip(n) for n in range(5)], cap=2)
    proofs = {}

    rows = list(NpsContent(key="nps_audio", club="nps", type="podcasts").rows(proofs))

    assert [row["id"] for row in rows] == [clip(n)["id"] for n in range(5)]
    assert [params["start"] for params in server.asked] == ["0", "2", "4"], "steps by rows returned, not by limit"
    assert proofs == {"raw_nps__nps_audio": 5}
    assert all("parkCode" not in params for params in server.asked), "a row with no park codes reads the national list"


def test_an_nps_rows_person_fields_never_land(registry, key, requests_mock):
    FakeList(requests_mock, AUDIO, [clip(1)])

    rows = list(NpsContent(key="nps_audio", club="nps", type="podcasts").rows({}))

    assert "transcript" not in rows[0] and "Fixture life story" not in json.dumps(rows)
    assert rows[0]["relatedParks"] == [{"parkCode": "semo"}], "nested values land as served, for dbt"


def test_an_nps_list_takes_its_park_codes_from_the_row_it_names(registry, key, requests_mock):
    asset = {"id": "a-1", "title": "Fixture photo", "credit": "NPS photo", "constraintsInfo": {"constraint": "Public domain"}}
    server = FakeList(requests_mock, ASSETS, [asset])

    rows = list(replace(nps_content("nps_assets"), club="nps", type="photos").rows({}))

    assert {params["parkCode"] for params in server.asked} == {"lecl,semo"}
    assert rows[0]["credit"] == "NPS photo" and rows[0]["constraintsInfo"] == {"constraint": "Public domain"}, (
        "a photo's own credit and licence land as NPS states them"
    )


def test_a_repeated_nps_id_refuses_the_read(registry, key, requests_mock):
    """Repeated on the second read as well, so the list is refused and its last committed table stands."""
    requests_mock.get(AUDIO, json={"total": "2", "data": [clip(1), clip(1)]})

    with pytest.raises(RuntimeError, match="missing or repeated"):
        list(NpsContent(key="nps_audio", club="nps", type="podcasts").rows({}))
    assert requests_mock.call_count == 2, "read twice, then refused"


def test_an_nps_list_that_repeats_an_id_on_its_first_read_is_read_again_and_the_second_read_lands(
    registry, key, requests_mock, capsys
):
    """NPS's start/limit order wobbled at a page boundary in monthly runs 17 and 18, and nps_things_to_do never landed.

    The first read's second page repeats clip 1 in place of clip 2; the
    second read is whole. Before the fix the first repeat refused the list
    with no second read (review finding EXD-9).
    """
    server = FakeList(requests_mock, AUDIO, [clip(n) for n in range(5)], cap=2)
    real_answer = server.answer

    def wobbles_once(request, context):
        answer = real_answer(request, context)
        if len(server.asked) == 2:
            answer["data"] = [clip(1), clip(3)]
        return answer

    requests_mock.get(AUDIO, json=wobbles_once)
    proofs = {}

    rows = list(NpsContent(key="nps_audio", club="nps", type="podcasts").rows(proofs))

    assert [row["id"] for row in rows] == [clip(n)["id"] for n in range(5)]
    assert proofs == {"raw_nps__nps_audio": 5}
    assert [params["start"] for params in server.asked] == ["0", "2", "0", "2", "4"], "the second read starts again at 0"
    assert "reading the list again, once" in capsys.readouterr().out


def cut_short(server: FakeList, cuts: int, declared: bool):
    """`server`'s answers as text, the first `cuts` of them stopped at 16,384 characters' worth of their body.

    Shaped like nps_multimedia_audio's refusals in monthly runs 18 and 19
    (refresh-reference.yml 37245577210 and 37253303123): 1,966,080 and
    163,840 bytes, each a whole multiple of 16,384, ending inside a string.
    Here a page is cut at its own halfway mark, which ends inside a string
    too. With `declared`, each answer's Content-Length states the whole
    body's length, so a cut one arrives short of what its header promised.
    """
    answered = []

    def answer(request, context):
        body = json.dumps(server.answer(request, context))
        context.headers["Content-Type"] = "application/json;charset=utf-8"
        if declared:
            context.headers["Content-Length"] = str(len(body))
        answered.append(len(body))
        if len(answered) <= cuts:
            return body[: len(body) // 2]
        return body

    return answer


def test_an_nps_page_that_arrives_cut_short_is_asked_for_once_more_and_the_whole_list_lands(registry, key, requests_mock, capsys):
    """nps_multimedia_audio was refused in monthly runs 16 to 19 on one page whose body stopped mid-string.

    The first answer to the first page is cut; asked again, through
    _json_apis._get's per-host gap, the page arrives whole and the list
    lands. Before the fix one cut page refused the whole list.
    """
    server = FakeList(requests_mock, AUDIO, [clip(n) for n in range(5)], cap=2)
    requests_mock.get(AUDIO, text=cut_short(server, cuts=1, declared=False))
    proofs = {}

    rows = list(NpsContent(key="nps_audio", club="nps", type="podcasts").rows(proofs))

    assert [row["id"] for row in rows] == [clip(n)["id"] for n in range(5)]
    assert proofs == {"raw_nps__nps_audio": 5}
    assert [params["start"] for params in server.asked] == ["0", "0", "2", "4"], "only the cut page is asked again"
    assert "asking for it once more" in capsys.readouterr().out


def test_an_nps_page_cut_short_twice_is_refused_naming_how_far_short_of_its_content_length_it_stopped(
    registry, key, requests_mock
):
    """A second cut answer refuses the list, as one cut answer did before, so a list missing a page never lands."""
    server = FakeList(requests_mock, AUDIO, [clip(n) for n in range(5)], cap=2)
    requests_mock.get(AUDIO, text=cut_short(server, cuts=2, declared=True))

    with pytest.raises(ValueError, match=r"not JSON: [\d,]+ bytes, .*bytes short of the [\d,]+ its Content-Length states"):
        list(NpsContent(key="nps_audio", club="nps", type="podcasts").rows({}))
    assert requests_mock.call_count == 2, "asked twice, then refused"


def test_an_unparsed_answer_with_no_content_length_says_there_was_nothing_to_compare_it_against(requests_mock):
    requests_mock.get(AUDIO, text='{"data": ["cut', headers={"Content-Type": "application/json"})

    with pytest.raises(ValueError, match="no Content-Length to compare against"):
        _json_apis._json(_json_apis._get(AUDIO), "nps_audio")


def test_without_an_nps_key_a_content_list_is_unavailable_and_nothing_is_asked(registry, requests_mock, monkeypatch):
    monkeypatch.delenv(_json_apis.NPS_API_KEY_ENV, raising=False)

    with pytest.raises(Unavailable, match="NPS_API_KEY"):
        NpsContent(key="nps_audio", club="nps", type="podcasts").change_check(None)
    assert requests_mock.call_count == 0


def test_a_park_codes_from_row_with_no_codes_is_refused_at_import(registry, tmp_path, monkeypatch):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"sources": [{"key": "bad", "url": ASSETS, "park_codes_from": "empty"}, {"key": "empty", "url": ALERTS}]})
    )
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()

    with pytest.raises(KeyError, match="lists no `park_codes`"):
        nps_content("bad")


# --- WordPress: a guide's child pages, and a hike type's terms ---------------------------------------------------


def test_a_guides_child_pages_are_read_by_their_parent_with_the_sites_own_count(registry, requests_mock):
    pages = [
        {
            "id": n,
            "modified_gmt": "2026-09-01T00:00:00",
            "slug": f"p{n}",
            "title": {"rendered": f"Trail {n}"},
            "content": {"rendered": "<p>Fixture leader, 555-0100</p>"},
            "author": 3,
        }
        for n in (1, 2)
    ]
    requests_mock.get(f"{SITE}/wp-json/wp/v2/pages", json=pages, headers={"X-WP-Total": "2", "X-WP-TotalPages": "1"})
    resource = replace(wordpress_child_pages("guide_pages", parent=2040), club="testclub", type="suggested_hikes")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert [query(r)["parent"] for r in requests_mock.request_history] == ["2040"]
    assert [row["id"] for row in rows] == [1, 2] and proofs == {"raw_testclub__guide_pages": 2}
    assert all("author" not in row for row in rows), "WP_DROPPED still applies"


def test_a_child_pages_read_needs_its_parent():
    with pytest.raises(ValueError, match="parent page's id"):
        wordpress_child_pages("guide_pages", parent=0)


def test_a_hike_types_terms_ride_the_types_monthly_lane_and_land_each_taxonomy(registry, requests_mock):
    for taxonomy in ("difficulty", "region"):
        requests_mock.get(
            f"{SITE}/wp-json/wp/v2/{taxonomy}",
            json=[{"id": 7, "name": f"Fixture {taxonomy}", "slug": taxonomy, "count": 1}],
            headers={"X-WP-Total": "1", "X-WP-TotalPages": "1"},
        )
    resource = replace(site_terms("club_hikes", ("difficulty", "region")), club="testclub", type="suggested_hikes")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert resource.cadence == "monthly" and resource.cadence_override is None
    assert resource.table == "raw_testclub__club_hikes_terms" and resource.part == "terms"
    assert [(row["taxonomy"], row["name"]) for row in rows] == [
        ("difficulty", "Fixture difficulty"),
        ("region", "Fixture region"),
    ]
    assert proofs == {"raw_testclub__club_hikes_terms": 2}


def test_an_empty_taxonomy_is_a_broken_read_not_an_empty_vocabulary(registry, requests_mock):
    requests_mock.get(f"{SITE}/wp-json/wp/v2/difficulty", json=[], headers={"X-WP-Total": "0", "X-WP-TotalPages": "0"})
    resource = SiteTerms(key="club_hikes", club="testclub", type="suggested_hikes", taxonomies=("difficulty",))

    with pytest.raises(RuntimeError, match="came back empty"):
        list(resource.rows({}))


# --- MediaWiki: two templates on one wiki ------------------------------------------------------------------------


def test_two_templates_on_one_wiki_are_two_reads_not_one_dataset_twice(registry):
    notices = _json_apis.mediawiki_announcements("wiki_notices")
    trails = mediawiki_template_pages("wiki_trails")

    assert isinstance(trails, MediawikiTemplatePages) and trails.template == "Template:Trail"
    assert (notices.api, notices.part) != (trails.api, trails.part), "the layout test tells the reads apart by part"
    assert trails.part == "Template:Trail"


def test_the_content_module_is_what_the_registrys_content_rows_are_read_with():
    """Every section C resource the club folders declare is one of this module's readers or an existing kind."""
    kinds = (PodcastEpisodes, NpsContent, WordpressChildPages, SiteTerms, MediawikiTemplatePages, _kinds.WordpressPosts)
    content = [r for r in all_resources(discover()) if type(r).__module__ == _content.__name__]
    assert content and all(isinstance(r, kinds) for r in content)
    assert {r.type for r in content} <= {"podcasts", "photos", "challenges", "suggested_hikes"}


def test_a_feed_item_is_parsed_as_xml_and_never_as_text():
    """ElementTree, as PodcastFeed parses: a tag's namespace is its own, so `itunes:author` is never a plain `author`."""
    item = ElementTree.fromstring(feed(items=1)).find("channel/item")
    tags = {child.tag for child in item}
    assert "{http://www.itunes.com/dtds/podcast-1.0.dtd}author" in tags and "author" in tags


def test_the_fixture_answers_ask_for_the_page_npscontent_asks_for():
    """make_dbt_fixtures.py writes NPS_CONTENT_PAGE_SIZE out by hand, so a change to the constant must reach it.

    3835ff58 moved the page from 500 to 100, and the pytest job's fixture-mode build then had no answer for any
    NPS content list (pipeline-tests.yml run 37253264657).
    """
    import make_dbt_fixtures
    from extract._content import NPS_CONTENT_PAGE_SIZE

    for name, text in make_dbt_fixtures._content_nps_fixtures().items():
        (answer,) = json.loads(text)["answers"]
        assert answer["query"]["limit"] == str(NPS_CONTENT_PAGE_SIZE), name
