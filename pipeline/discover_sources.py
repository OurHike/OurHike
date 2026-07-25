"""Discover ArcGIS FeatureServer layer URLs behind an Experience Builder app
and write/update sources.json.

ArcGIS Experience Builder apps (like the ATC's public map) don't expose a
plain list of data downloads - the layer URLs live inside the app's web map,
which itself is only reachable by walking the app's config. This script walks
that chain the same way a browser resolves it at load time:

    Experience app item -> app config -> dataSources (WEB_MAP entries)
    -> web map item -> web map data -> operationalLayers[].url

Usage:
    python discover_sources.py <experience-url-or-item-id> [--provider ATC]

Re-running against the same app updates urls/titles for existing keys (and
prints a note if a url changed) while preserving any hand-added fields like
"notes". Sources that disappear from the app are kept (not deleted) with a
warning, since that likely means the app changed, not that the layer is gone.
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "sources.json"

REGISTRY_COMMENT = (
    "Registry of upstream data sources for the OurHike pipeline. Generated/updated "
    "by discover_sources.py - re-run that script rather than hand-editing urls here."
)


def extract_item_id(url_or_id: str) -> str:
    if "/" not in url_or_id:
        return url_or_id
    parts = urlparse(url_or_id).path.strip("/").split("/")
    return parts[-1] if parts else url_or_id


def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r"^a\.t\.\s*", "", s)  # strip common "A.T." prefix for readable keys
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def fetch_json(url: str) -> dict:
    resp = requests.get(url, params={"f": "json"}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def discover_layers(experience_url_or_id: str) -> tuple[list[dict], str]:
    item_id = extract_item_id(experience_url_or_id)
    app_config = fetch_json(f"https://www.arcgis.com/sharing/rest/content/items/{item_id}/data")
    data_sources = app_config.get("dataSources", {})

    web_maps = [ds for ds in data_sources.values() if ds.get("type") == "WEB_MAP"]
    if not web_maps:
        raise RuntimeError(f"No WEB_MAP data sources found in experience app {item_id}")

    layers = []
    seen_urls = set()
    for ds in web_maps:
        portal_url = ds["portalUrl"].rstrip("/")
        webmap_id = ds["itemId"]
        webmap_data = fetch_json(f"{portal_url}/sharing/rest/content/items/{webmap_id}/data")
        for layer in webmap_data.get("operationalLayers", []):
            url = layer.get("url")
            title = layer.get("title")
            if not url or not title or url in seen_urls:
                continue
            seen_urls.add(url)
            layers.append({"title": title, "url": url, "webmap_item": webmap_id})
    return layers, item_id


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experience", help="Experience Builder URL or item ID, e.g. https://experience.arcgis.com/experience/<id>")
    parser.add_argument("--provider", default="ATC", help="Provider label to store on newly discovered sources (default: ATC)")
    args = parser.parse_args()

    print(f"Discovering layers behind experience app {args.experience} ...")
    layers, item_id = discover_layers(args.experience)
    print(f"Found {len(layers)} layers.")

    existing = {}
    if SOURCES_PATH.exists():
        registry = json.loads(SOURCES_PATH.read_text())
        existing = {s["key"]: s for s in registry.get("sources", [])}

    today = date.today().isoformat()
    new_sources = []
    seen_keys = set()
    for layer in layers:
        key = slugify(layer["title"])
        seen_keys.add(key)
        prior = existing.get(key, {})
        if prior.get("url") and prior["url"] != layer["url"]:
            print(f"  NOTE: {key} url changed\n    old: {prior['url']}\n    new: {layer['url']}")
        entry = {
            "key": key,
            "title": layer["title"],
            "provider": prior.get("provider", args.provider),
            "url": layer["url"],
            "discovered_via": (
                f"Experience Builder app {item_id} -> Web Map item "
                f"{layer['webmap_item']} -> operationalLayers"
            ),
            "discovered_date": today,
        }
        if "notes" in prior:
            entry["notes"] = prior["notes"]
        new_sources.append(entry)

    missing_keys = set(existing) - seen_keys
    for key in sorted(missing_keys):
        print(f"  WARNING: previously registered source '{key}' was not found in this app - kept as-is, check manually")
        new_sources.append(existing[key])

    SOURCES_PATH.write_text(json.dumps({"_comment": REGISTRY_COMMENT, "sources": new_sources}, indent=2) + "\n")
    print(f"Wrote {len(new_sources)} sources -> {SOURCES_PATH}")


if __name__ == "__main__":
    main()
