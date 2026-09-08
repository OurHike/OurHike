"""fetch_nynjtc_long_path_guide.py - the registry-driven section-guide fetch (#1288).

Everything here runs against a temp directory and a stubbed HTTP layer - never
nynjtc.org (TESTING.md). The pages are synthetic, in the real skeleton; the
parser they feed is tested against markup in test_nynjtc_long_path_guide.py.

The behaviours worth pinning are the fetcher's promises, not requests
plumbing: the index decides which pages exist; a 304 and an unchanged body
are both "up to date"; a page that no longer parses leaves the previous
cache, sections.json and manifest exactly as they were and fails the run;
and an unregistered source is an exit, not a fetch of a hard-coded URL.
"""

from __future__ import annotations

import json

import pytest

import fetch_nynjtc_long_path_guide as fetcher

ENTRY = {
    "key": "nynjtc_long_path_guide",
    "kind": "guide_pages",
    "provider": "NYNJTC",
    "url": "https://example.test/guide/",
    "reaches_hikers": False,
}


def section_page(number: int, description: str = "<p><strong>0.55</strong> Pass a spring to the left of the trail.</p>") -> str:
    def block(name, inner):
        return f"<details><summary>{name}</summary>{inner}</details>"

    return (
        f"<main><h1>The Long Path &#8211; Section {number}</h1><h2>A to B</h2>"
        "<p><strong>Distance:</strong> 8.4 miles<br><strong>Parks:</strong> P</p>"
        f"{block('Access', '<p>drive</p>')}"
        f"{block('Parking', '<p><strong>0.00</strong> Lot at the road. (41.96556°, -74.45248°)</p>')}"
        f"{block('Camping', '<p>None.</p>')}"
        f"{block('Detailed Trail Description', description)}</main>"
    )


INDEX = '<main><a href="/lp-section-1/">Section 1</a><a href="/lp-section-2/">Section 2</a></main>'


class FakeResponse:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    registry_path = tmp_path / "sources.json"
    registry_path.write_text(json.dumps({"sources": [ENTRY]}))
    out_dir = tmp_path / "raw" / "nynjtc_long_path_guide"
    monkeypatch.setattr(fetcher, "SOURCES_PATH", registry_path)
    monkeypatch.setattr(fetcher, "OUT_DIR", out_dir)
    monkeypatch.setattr(fetcher, "MANIFEST_PATH", out_dir / "manifest.json")
    monkeypatch.setattr(fetcher, "SECTIONS_PATH", out_dir / "sections.json")
    monkeypatch.setattr(fetcher, "THROTTLE_SECONDS", 0)
    recorded = []
    monkeypatch.setattr(fetcher, "record", lambda name, paths, root=None: recorded.append((name, list(paths))))
    return {"registry_path": registry_path, "out_dir": out_dir, "recorded": recorded}


def stub_http(monkeypatch, pages: dict[str, FakeResponse]):
    """URL -> response; records the headers each call sent."""
    calls = []

    def fake_request(url, *, session=None, headers=None, **kwargs):
        calls.append({"url": url, "headers": headers or {}})
        return pages[url]

    monkeypatch.setattr(fetcher, "request_with_retry", fake_request)
    return calls


def test_fetches_parses_and_manifests_every_page_the_index_links(sandbox, monkeypatch):
    calls = stub_http(
        monkeypatch,
        {
            "https://example.test/guide/": FakeResponse(text=INDEX),
            "https://www.nynjtc.org/lp-section-1/": FakeResponse(text=section_page(1), headers={"ETag": '"one"'}),
            "https://www.nynjtc.org/lp-section-2/": FakeResponse(text=section_page(2)),
        },
    )
    fetcher.main()
    out = sandbox["out_dir"]
    assert [c["url"] for c in calls] == [
        "https://example.test/guide/",
        "https://www.nynjtc.org/lp-section-1/",
        "https://www.nynjtc.org/lp-section-2/",
    ]
    sections = json.loads((out / "sections.json").read_text())
    assert [s["number"] for s in sections] == [1, 2]
    assert sections[0]["parking"][0]["lat"] == 41.96556
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["pages"]["lp-section-1"]["etag"] == '"one"'
    assert (out / "lp-section-2.html").read_text() == section_page(2)
    assert sandbox["recorded"][0][0] == "fetch_nynjtc_long_path_guide"


def test_a_304_reads_the_cached_page_back_rather_than_the_wire(sandbox, monkeypatch):
    stub_http(
        monkeypatch,
        {
            "https://example.test/guide/": FakeResponse(text=INDEX),
            "https://www.nynjtc.org/lp-section-1/": FakeResponse(text=section_page(1), headers={"ETag": '"one"'}),
            "https://www.nynjtc.org/lp-section-2/": FakeResponse(text=section_page(2)),
        },
    )
    fetcher.main()
    calls = stub_http(
        monkeypatch,
        {
            "https://example.test/guide/": FakeResponse(text=INDEX),
            "https://www.nynjtc.org/lp-section-1/": FakeResponse(status_code=304),
            "https://www.nynjtc.org/lp-section-2/": FakeResponse(text=section_page(2)),
        },
    )
    fetcher.main()
    assert calls[1]["headers"] == {"If-None-Match": '"one"'}
    assert calls[2]["headers"] == {}, "a page that served no validator is asked for plainly"
    sections = json.loads((sandbox["out_dir"] / "sections.json").read_text())
    assert [s["number"] for s in sections] == [1, 2]


def test_a_page_that_stops_parsing_keeps_the_previous_cache_and_fails_the_run(sandbox, monkeypatch):
    stub_http(
        monkeypatch,
        {
            "https://example.test/guide/": FakeResponse(text=INDEX),
            "https://www.nynjtc.org/lp-section-1/": FakeResponse(text=section_page(1)),
            "https://www.nynjtc.org/lp-section-2/": FakeResponse(text=section_page(2)),
        },
    )
    fetcher.main()
    before = {p.name: p.read_text() for p in sandbox["out_dir"].iterdir()}

    redesigned = section_page(2).replace("<summary>Camping</summary>", "<summary>Overnight</summary>")
    stub_http(
        monkeypatch,
        {
            "https://example.test/guide/": FakeResponse(text=INDEX),
            "https://www.nynjtc.org/lp-section-1/": FakeResponse(text=section_page(1)),
            "https://www.nynjtc.org/lp-section-2/": FakeResponse(text=redesigned),
        },
    )
    with pytest.raises(ValueError, match="Camping"):
        fetcher.main()
    after = {p.name: p.read_text() for p in sandbox["out_dir"].iterdir()}
    assert after == before, "a half-updated cache is not a state this fetcher may leave behind"


def test_an_unregistered_source_is_an_exit_not_a_fetch(sandbox, monkeypatch):
    sandbox["registry_path"].write_text(json.dumps({"sources": []}))
    calls = stub_http(monkeypatch, {})
    with pytest.raises(SystemExit):
        fetcher.main()
    assert calls == []


def test_a_regenerated_gallery_id_is_not_a_change_but_a_moved_spring_is(sandbox, monkeypatch, capsys):
    """WordPress mints a random galleryId per render, so the body hash reads
    every page as changed on every run (measured 2026-09-08); the parse does
    not move unless the facts do."""
    stub_http(
        monkeypatch,
        {
            "https://example.test/guide/": FakeResponse(text=INDEX),
            "https://www.nynjtc.org/lp-section-1/": FakeResponse(text=section_page(1)),
            "https://www.nynjtc.org/lp-section-2/": FakeResponse(text=section_page(2)),
        },
    )
    fetcher.main()
    rerendered = section_page(2).replace(
        "<main>", '<main><figure data-wp-context="{&quot;galleryId&quot;:&quot;6aa0648feec2e&quot;}"><img src="x.jpg"></figure>'
    )
    stub_http(
        monkeypatch,
        {
            "https://example.test/guide/": FakeResponse(text=INDEX),
            "https://www.nynjtc.org/lp-section-1/": FakeResponse(text=section_page(1)),
            "https://www.nynjtc.org/lp-section-2/": FakeResponse(text=rerendered),
        },
    )
    fetcher.main()
    assert "0 section(s) whose parsed content changed" in capsys.readouterr().out
    moved = section_page(2, description="<p><strong>0.60</strong> Pass a spring to the left of the trail.</p>")
    stub_http(
        monkeypatch,
        {
            "https://example.test/guide/": FakeResponse(text=INDEX),
            "https://www.nynjtc.org/lp-section-1/": FakeResponse(text=section_page(1)),
            "https://www.nynjtc.org/lp-section-2/": FakeResponse(text=moved),
        },
    )
    fetcher.main()
    assert "1 section(s) whose parsed content changed since the last run: [2]" in capsys.readouterr().out
