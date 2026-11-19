"""Fetch, licence-check, review and treat the field-card plates from plates_manifest.json.

Runs where the network is open (a Claude Code session, the maintainer's machine), never in
the design workspace. Three stages, each a command, so a human eye sits between finding a
photograph and shipping it:

    python3 fetch_plates.py fetch    plates_manifest.json work/     # download every candidate, re-check its licence
    python3 fetch_plates.py sheet    plates_manifest.json work/     # one contact sheet per type: candidate beside its caption
    python3 fetch_plates.py treat    plates_manifest.json work/ client/src/design-system/assets/plates/
                                                                    # approved candidates -> duotone plates + plates.ts

Approval is a field in the manifest: set "approved": true on the candidate that really shows
the scenario in the caption (and only that), after looking at the sheet. The treat stage
refuses a plate with no approved candidate and lists them, which is the shot list for the
club. Nothing here guesses: a photograph of a sound bridge is never used for "abutment
scoured" because it was the only bridge found.

Licence gate: the same one as client/src/lib/heroPhotos.ts — public domain, CC0, CC BY or
CC BY-SA, any version; never NC, never ND, never unknown. For a Wikimedia Commons file the
licence is read again from the API at fetch time, not trusted from the manifest. For any
other source the manifest's licence string is checked against the gate and the page URL is
kept in the credit so a reviewer can look.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from duotone import duotone, square_crop  # noqa: E402

UA = "OurHike-plates/1 (https://ourhike.org; maintainer contact in repo README)"
ALLOWED = re.compile(r"^(public domain|pd|cc0|cc[- ]by(-sa)?)([- ]\d\.\d)?", re.I)
REFUSED = re.compile(r"(nc|nd|non-?commercial|no ?deriv|all rights reserved|fair use|unknown)", re.I)
COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def licence_ok(text):
    t = (text or "").strip().replace("Creative Commons Attribution-Share Alike", "CC BY-SA").replace(
        "Creative Commons Attribution", "CC BY").replace("Public domain", "public domain")
    if REFUSED.search(t):
        return False
    return bool(ALLOWED.search(t))


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if binary else data.decode("utf-8")


def commons_info(page_url):
    """Licence, author and the direct URL of a Commons file, from the API."""
    title = urllib.parse.unquote(page_url.rsplit("/", 1)[-1])
    if not title.startswith("File:"):
        title = "File:" + title
    q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "imageinfo",
                                "iiprop": "extmetadata|url", "iiurlwidth": 2000, "format": "json"})
    data = json.loads(get(f"{COMMONS_API}?{q}"))
    page = next(iter(data["query"]["pages"].values()))
    info = page["imageinfo"][0]
    meta = info.get("extmetadata", {})
    licence = meta.get("LicenseShortName", {}).get("value", "")
    author = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
    return {"licence": licence, "author": author, "file_url": info.get("thumburl") or info["url"]}


def load(manifest_path):
    with open(manifest_path) as f:
        return json.load(f)


def save(manifest_path, items):
    with open(manifest_path, "w") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def slot(item):
    return f"{item['type']}-{item['plate']}"


def fetch(manifest_path, work):
    items = load(manifest_path)
    os.makedirs(work, exist_ok=True)
    for it in items:
        if it.get("rank", 0) == 0:
            continue
        name = f"{slot(it)}-r{it['rank']}.jpg"
        path = os.path.join(work, name)
        try:
            if it.get("source") == "commons":
                info = commons_info(it["page_url"])
                it.update(info)
            if not licence_ok(it.get("licence")):
                it["status"] = f"refused: licence '{it.get('licence')}'"
                print("REFUSED", name, it["status"])
                continue
            if not it.get("file_url"):
                it["status"] = "no file url"
                print("SKIP", name, it["status"])
                continue
            if not os.path.exists(path):
                open(path, "wb").write(get(it["file_url"], binary=True))
            it["local"] = name
            it["status"] = "fetched"
            print("ok", name, it["licence"])
        except Exception as e:  # noqa: BLE001 - a bad candidate must not stop the batch
            it["status"] = f"error: {e}"
            print("ERROR", name, e)
    save(manifest_path, items)


def sheet(manifest_path, work):
    items = [i for i in load(manifest_path) if i.get("local")]
    by_type = {}
    for it in items:
        by_type.setdefault(it["type"], []).append(it)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except Exception:  # noqa: BLE001
        font = None
    for t, rows in by_type.items():
        rows.sort(key=lambda i: (i["plate"], i["rank"]))
        W, H = 320, 320
        img = Image.new("RGB", (W * 3 + 40, (H + 70) * len(rows) + 20), "#f7f3e9")
        d = ImageDraw.Draw(img)
        for n, it in enumerate(rows):
            y = 10 + n * (H + 70)
            try:
                im = square_crop(Image.open(os.path.join(work, it["local"])), it.get("crop_box"))
                im = im.resize((W, H))
                img.paste(im, (10, y))
            except Exception as e:  # noqa: BLE001
                d.text((20, y + 20), f"unreadable: {e}", fill="#994e15", font=font)
            d.text((10, y + H + 6), f"{slot(it)} r{it['rank']}  {it['plate_text']}", fill="#122016", font=font)
            d.text((10, y + H + 26), f"{it.get('author', '')} · {it.get('licence', '')}", fill="#5a5346", font=font)
            d.text((10, y + H + 46), (it.get("shows") or "")[:110], fill="#5a5346", font=font)
        out = os.path.join(work, f"sheet-{t}.png")
        img.save(out)
        print("wrote", out)


REGISTRY_HEAD = '''// Generated by features/structure-inventory-handoff/tools/fetch_plates.py from the
// approved rows of plates_manifest.json. Every plate here passed the licence gate
// (public domain, CC0, CC BY or CC BY-SA; never NC, never ND) and a human looked at it
// against its caption before approving it. The credit renders under the plate.
export type Plate = { type: string; index: number; caption: string; src: string; credit: string; page: string }
export const PLATES: Plate[] = [
'''


def treat(manifest_path, work, out_dir):
    items = load(manifest_path)
    approved = [i for i in items if i.get("approved") and i.get("local")]
    wanted = {(i["type"], i["plate"]): i["plate_text"] for i in items}
    done = set()
    rows = []
    for it in approved:
        key = (it["type"], it["plate"])
        if key in done:
            raise SystemExit(f"two approved candidates for {slot(it)}; approve one")
        done.add(key)
        d = os.path.join(out_dir, it["type"])
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, f"{it['plate']}.jpg")
        im = duotone(square_crop(Image.open(os.path.join(work, it["local"])), it.get("crop_box")))
        im.save(dst, quality=84, optimize=True)
        credit = f"Photo: {it.get('author', '').strip() or 'unknown'} · {it.get('licence', '')}"
        rows.append(f"  {{ type: '{it['type']}', index: {it['plate']}, caption: {json.dumps(it['plate_text'])}, "
                    f"src: '{it['type']}/{it['plate']}.jpg', credit: {json.dumps(credit)}, page: {json.dumps(it['page_url'])} }},")
        print("plate", dst, credit)
    with open(os.path.join(out_dir, "plates.ts"), "w") as f:
        f.write(REGISTRY_HEAD + "\n".join(rows) + "\n]\n")
    missing = sorted(k for k in wanted if k not in done)
    print(f"\n{len(done)} plates written, {len(missing)} still wanted:")
    for k in missing:
        print(f"  {k[0]}-{k[1]}  {wanted[k]}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "fetch":
        fetch(sys.argv[2], sys.argv[3])
    elif cmd == "sheet":
        sheet(sys.argv[2], sys.argv[3])
    elif cmd == "treat":
        treat(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(__doc__)
