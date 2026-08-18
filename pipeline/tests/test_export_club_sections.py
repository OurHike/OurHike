"""The exporter's publish contract (#659): its manifest must work from any
CWD and its main() must answer like its siblings.

The assembly logic itself is tested where it lives, in
test_lib_club_sections.py - this file covers only the seam publish.py
reads, which is where the audit found the faults: a relative manifest path
(every sibling stores absolute, and publish.py resolves the string against
its own CWD) and a main() returning the artifact body where every sibling
returns its manifest.
"""

import hashlib
import json
import os
from pathlib import Path

import export_club_sections


def test_the_manifest_path_is_absolute_and_main_returns_the_manifest(tmp_path, monkeypatch):
    out_path = tmp_path / "processed" / "club_sections.json"
    manifest_path = tmp_path / "processed" / "club_sections_manifest.json"
    monkeypatch.setattr(export_club_sections, "OUT_PATH", out_path)
    monkeypatch.setattr(export_club_sections, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(
        export_club_sections,
        "build_output",
        lambda: {"sources": {}, "clubs": [], "unattributed": []},
    )
    # Publishes happen from repo root, not pipeline/ - the CWD that made the
    # old relative path crash publish.py mid-collect.
    monkeypatch.chdir(tmp_path)

    returned = export_club_sections.main()

    manifest = json.loads(manifest_path.read_text())
    assert Path(manifest["path"]).is_absolute(), "a relative manifest path resolves against publish.py's CWD, not pipeline/"
    assert Path(manifest["path"]).exists(), "the path must reach the artifact from any CWD"
    assert manifest["sha256"] == hashlib.sha256(out_path.read_bytes()).hexdigest()
    assert returned == manifest, "main() answers with the manifest, like every sibling exporter"
    assert os.getcwd() != str(Path(export_club_sections.__file__).parent), (
        "fixture guard: this test must NOT run from pipeline/, or the CWD claim above proves nothing"
    )
