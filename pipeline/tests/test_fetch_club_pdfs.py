"""fetch_club_pdfs.py - the registry-driven club-PDF fetch (#669).

Everything here runs against a temp directory and a stubbed HTTP layer -
never the real GATC site, never a real PDF (TESTING.md). extract_page_texts
is stubbed too, so these tests need no pypdf: the module keeps that import
lazy on purpose (requirements.in explains), and the parser it feeds is
tested against text in test_lib_club_pdfs.py.

The behaviours worth pinning are the fetcher's promises, not requests
plumbing: only club_pdf entries are fetched at all; a parse failure leaves
the previous PDF, rows and manifest exactly as they were; a 304 and an
unchanged body are both "up to date" rather than re-parses; and one club's
broken document does not stop another club's fetch.
"""

from __future__ import annotations

import json

import pytest

import fetch_club_pdfs


class FakeResponse:
    def __init__(self, status_code=200, content=b"", headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Point every path constant into tmp_path and neutralise the receipt -
    the receipt writer is lib/fetch_receipts' concern, tested there."""
    registry_path = tmp_path / "sources.json"
    out_dir = tmp_path / "raw" / "club_pdfs"
    monkeypatch.setattr(fetch_club_pdfs, "SOURCES_PATH", registry_path)
    monkeypatch.setattr(fetch_club_pdfs, "OUT_DIR", out_dir)
    monkeypatch.setattr(fetch_club_pdfs, "MANIFEST_PATH", out_dir / "manifest.json")
    recorded = []
    monkeypatch.setattr(fetch_club_pdfs, "record", lambda name, paths: recorded.append((name, list(paths))))
    return {"registry_path": registry_path, "out_dir": out_dir, "recorded": recorded}


def write_registry(path, sources):
    path.write_text(json.dumps({"sources": sources}))


GATC_ENTRY = {
    "key": "gatc_water_sources",
    "kind": "club_pdf",
    "provider": "GATC",
    "url": "https://example.test/GATC_Water_Sources.pdf",
}

PARSEABLE_PAGES = ["Mile Point Source Name Distance Off AT\n1.6 Davis Creek On-Trail"]


def stub_http(monkeypatch, responses):
    """queue of FakeResponses; records the headers each call sent."""
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append({"url": url, "headers": headers or {}})
        return responses.pop(0)

    monkeypatch.setattr(fetch_club_pdfs.requests, "get", fake_get)
    return calls


def test_fetches_parses_and_manifests_a_registered_pdf(sandbox, monkeypatch):
    write_registry(sandbox["registry_path"], [GATC_ENTRY, {"key": "shelters", "url": "https://arcgis.example/4"}])
    stub_http(monkeypatch, [FakeResponse(content=b"%PDF-fake", headers={"ETag": '"v1"'})])
    monkeypatch.setattr(fetch_club_pdfs, "extract_page_texts", lambda body: PARSEABLE_PAGES)

    assert fetch_club_pdfs.main() == 0

    assert (sandbox["out_dir"] / "gatc_water_sources.pdf").read_bytes() == b"%PDF-fake"
    rows_doc = json.loads((sandbox["out_dir"] / "gatc_water_sources.json").read_text())
    assert rows_doc["rows"] == [{"mile": 1.6, "entry": "Davis Creek On-Trail", "trail": "at"}]
    assert "review and cross-checks only" in rows_doc["licence_note"].lower()
    manifest = json.loads((sandbox["out_dir"] / "manifest.json").read_text())
    assert manifest["gatc_water_sources"]["etag"] == '"v1"'
    assert manifest["gatc_water_sources"]["rows"] == 1
    # The ArcGIS entry was never requested - kind discrimination is the
    # registry's whole point (lib/source_registry.py).
    [(name, paths)] = sandbox["recorded"]
    assert name == "fetch_club_pdfs"
    assert len(paths) == 2


def test_only_club_pdf_entries_are_fetched(sandbox, monkeypatch):
    write_registry(sandbox["registry_path"], [{"key": "shelters", "url": "https://arcgis.example/4"}])
    calls = stub_http(monkeypatch, [])

    assert fetch_club_pdfs.main() == 0
    assert calls == []


def test_a_304_is_up_to_date_not_a_refetch(sandbox, monkeypatch):
    write_registry(sandbox["registry_path"], [GATC_ENTRY])
    sandbox["out_dir"].mkdir(parents=True)
    (sandbox["out_dir"] / "gatc_water_sources.pdf").write_bytes(b"%PDF-old")
    (sandbox["out_dir"] / "manifest.json").write_text(
        json.dumps({"gatc_water_sources": {"etag": '"v1"', "sha256": "irrelevant", "files": ["data/raw/club_pdfs/x"]}})
    )
    calls = stub_http(monkeypatch, [FakeResponse(status_code=304)])

    assert fetch_club_pdfs.main() == 0

    assert calls[0]["headers"]["If-None-Match"] == '"v1"'
    assert (sandbox["out_dir"] / "gatc_water_sources.pdf").read_bytes() == b"%PDF-old"


def test_recorded_state_without_the_pdf_on_disk_sends_no_conditionals(sandbox, monkeypatch):
    """A deleted download must refetch, not 304 forever against a ghost."""
    write_registry(sandbox["registry_path"], [GATC_ENTRY])
    sandbox["out_dir"].mkdir(parents=True)
    (sandbox["out_dir"] / "manifest.json").write_text(json.dumps({"gatc_water_sources": {"etag": '"v1"'}}))
    calls = stub_http(monkeypatch, [FakeResponse(content=b"%PDF-new")])
    monkeypatch.setattr(fetch_club_pdfs, "extract_page_texts", lambda body: PARSEABLE_PAGES)

    assert fetch_club_pdfs.main() == 0

    assert "If-None-Match" not in calls[0]["headers"]
    assert (sandbox["out_dir"] / "gatc_water_sources.pdf").exists()


def test_same_bytes_reserved_without_a_304_do_not_reparse(sandbox, monkeypatch):
    """WordPress does not always honour conditionals; identical bytes must
    not churn the rows file or the receipt's idea of what changed."""
    body = b"%PDF-same"
    import hashlib

    write_registry(sandbox["registry_path"], [GATC_ENTRY])
    sandbox["out_dir"].mkdir(parents=True)
    (sandbox["out_dir"] / "gatc_water_sources.pdf").write_bytes(body)
    (sandbox["out_dir"] / "manifest.json").write_text(
        json.dumps({"gatc_water_sources": {"sha256": hashlib.sha256(body).hexdigest(), "files": []}})
    )
    stub_http(monkeypatch, [FakeResponse(content=body, headers={"ETag": '"v2"'})])

    def explode(_body):
        raise AssertionError("unchanged bytes must not be re-parsed")

    monkeypatch.setattr(fetch_club_pdfs, "extract_page_texts", explode)

    assert fetch_club_pdfs.main() == 0

    manifest = json.loads((sandbox["out_dir"] / "manifest.json").read_text())
    # The fresh validator is kept so the next run's conditional can 304.
    assert manifest["gatc_water_sources"]["etag"] == '"v2"'


def test_a_parse_failure_keeps_the_previous_state_and_fails_the_run(sandbox, monkeypatch):
    write_registry(sandbox["registry_path"], [GATC_ENTRY])
    sandbox["out_dir"].mkdir(parents=True)
    (sandbox["out_dir"] / "gatc_water_sources.pdf").write_bytes(b"%PDF-good")
    (sandbox["out_dir"] / "gatc_water_sources.json").write_text('{"rows": []}')
    old_manifest = {"gatc_water_sources": {"sha256": "of-the-good-pdf", "files": []}}
    (sandbox["out_dir"] / "manifest.json").write_text(json.dumps(old_manifest))
    stub_http(monkeypatch, [FakeResponse(content=b"%PDF-reshuffled")])

    def broken_parse(_pages):
        raise ValueError("its layout has changed")

    monkeypatch.setattr(fetch_club_pdfs, "extract_page_texts", lambda body: ["whatever"])
    monkeypatch.setattr(fetch_club_pdfs, "PARSERS", {"gatc_water_sources": broken_parse})

    assert fetch_club_pdfs.main() == 1

    # Nothing moved: the known-good PDF, rows and manifest all survive the
    # broken upstream, and no receipt claims this run finished.
    assert (sandbox["out_dir"] / "gatc_water_sources.pdf").read_bytes() == b"%PDF-good"
    assert json.loads((sandbox["out_dir"] / "manifest.json").read_text()) == old_manifest
    assert sandbox["recorded"] == []


def test_one_broken_club_does_not_stop_anothers_fetch(sandbox, monkeypatch):
    second = {"key": "other_club_list", "kind": "club_pdf", "provider": "XYZ", "url": "https://example.test/other.pdf"}
    write_registry(sandbox["registry_path"], [GATC_ENTRY, second])
    stub_http(
        monkeypatch,
        [FakeResponse(status_code=503), FakeResponse(content=b"%PDF-two", headers={})],
    )
    monkeypatch.setattr(fetch_club_pdfs, "extract_page_texts", lambda body: PARSEABLE_PAGES)

    assert fetch_club_pdfs.main() == 1  # the run still fails, out loud

    # ...but the healthy club's PDF landed (no parser registered for it:
    # fetched-for-review is the kind's whole job).
    assert (sandbox["out_dir"] / "other_club_list.pdf").read_bytes() == b"%PDF-two"
    manifest = json.loads((sandbox["out_dir"] / "manifest.json").read_text())
    assert manifest["other_club_list"]["rows"] is None
    assert "gatc_water_sources" not in manifest
