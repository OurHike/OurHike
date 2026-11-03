"""Spike: can a hike be illustrated by looking its PLACE up by name?

**Strategies A and B** of #1450 - "Find a photograph for each of the 385 NYNJTC
hikes, using the names in their prose rather than a radius around their
trailhead". Its companion `spike_hike_photo_sources.py` measured strategy E,
the corpora you search by coordinate, and found them failing in opposite
directions: Panoramax has the right subject and no data, iNaturalist has forty
times the data and photographs organisms. This measures the other instrument -
**a name, resolved to a thing, whose picture somebody chose on purpose.**

WHY A NAME MIGHT SUCCEED WHERE A RADIUS FAILED. Every coordinate search shares
one flaw: proximity is not aboutness. A file 40 m from a shelter is a
photograph of whatever its uploader pointed at. Wikidata's P18 is the opposite
kind of object - a human picked one image to represent one entity, which is a
claim about SUBJECT rather than about distance. features/POI_PHOTOS.md's
2026-08-08 measurement says the same thing from the other end: proximity worked
for resupply towns (~18%) and nowhere else, "because a town is a big subject".
A park is a big subject too.

MEASURED 2026-09-15, over the ten parks this build can name without the export
(which is behind its site password, #1468). The funnel, because the endpoint
alone would be misleading:

    park names asked                 10
    resolved to a Wikidata entity    10
    ...that is actually that place   10
    carrying a P18 lead image        10   <- coverage is not the problem
    ...whose licence we may ship      2   <- SEVEN ARE CC BY-SA 3.0
    ...inside the 4-year freshness    0   <- and the last two are old

**THE SUBJECT IS RIGHT AND THE PAPERWORK IS WRONG**, which is the exact inverse
of strategy E and the reason this one is worth arguing about rather than
closing.

Every park resolved and every one carries a lead image. And the images are
GOOD - four were opened rather than trusted, and all four are photographs a
hiker would recognise as the place: Harriman leads with Island Pond, water and
rock and wooded hills; Ramapo Mountain with a stream running through spring
woods; Sterling Forest with its fire tower; Bear Mountain with the vista down
the Hudson from the summit. Against Panoramax's storm deadfall and
iNaturalist's leaf litter, that is a different class of result, and it is what
P18 being a HUMAN'S PICK rather than a proximity hit buys.

**A filename is not a subject, in both directions.** "Bear Mtn Bridge.jpg"
reads like a photograph of a bridge and is in fact the summit view every hiker
climbs that mountain for. The adversarial look that condemned two sources
rescued this one, which is the argument for doing it every time rather than
only when a result looks too good.

So what stops this is licensing and age:

  - **Seven of the ten are CC BY-SA 3.0.** POI_PHOTOS.md rejects the pre-4.0
    suite wholesale because a one-link credit line cannot meet its terms - the
    same wall that took 175 of 176 licence rejections in the 2026-08-08
    measurement, and the same one `spike_flickr_group.py` predicted for Flickr.
    Wikidata lead images are largely an older upload cohort and inherit it.
  - **The two survivors are stale anyway**: Sterling Forest's tower is
    2020-10-06 and Bear Mountain's vista is 1999-06-06, against a four-year
    `fetch_poi_images.MAX_PHOTO_AGE_DAYS`. Two more carry no capture date at
    all, which `lib/commons.parse_date_taken` treats as a verdict rather than a
    gap, correctly.

**Both walls are already-open questions rather than new ones**, which is why
this is a maintainer's call and not a code change:

  - features/POI_PHOTOS.md owes the freshness decision to the ATC inventory
    photos already - that whole corpus is 2007-2017, "the newest is
    2017-06-06, nine years past, and every single one fails
    MAX_PHOTO_AGE_DAYS" - and frames the answer as a per-source bar, because
    "proximity-matched strangers' photos and the trail-managing organisation's
    own documentation do not deserve the same freshness rule." **A landscape is
    the third case and the easiest of the three to argue: a ridge does not dry
    up like a spring or burn down like a shelter.** Island Pond looks today
    much as it did in 2006.
  - The pre-4.0 rejection is a judgement about whether a one-link credit can
    satisfy those terms, not a fact about the licence. It is written down in
    one place and could be revisited in one place.

**Nothing here decides either.** The spike reports both numbers - inside the
bars and ignoring them - so the cost of each is visible. Reporting only the
post-filter 0 of 10 would have read as "this does not work", and what it
actually says is "this works and we have ruled it out on paperwork".

RESOLVING A NAME IS NOT A STRING SEARCH, and this is where #1450's own probe
went wrong. That issue reports its landmark run "rate-limited (14 of 18
requests errored)" with a regex that over-captured, and its park run finding
8 of 20 by "naive exact-string search". Two failures are structural rather than
incidental, so this does them properly:

  - **The top hit is often the wrong thing.** "Sterling Forest" resolves first
    to Q7611404, *a human settlement in New York* - not the state park the
    hikes are in (checked live, 2026-09-15). Taking hit one would have scored
    a hamlet's photograph as the park's. So a candidate must prove itself:
    `P625` within `MAX_ENTITY_DRIFT_KM` of where we know the place to be,
    which is a fact the export gives us free and the string search threw away.

    **The guard refused nothing in the run above, and that is not evidence it
    is unnecessary.** This spike asks with full park names ("Sterling Forest
    State Park"), which resolve cleanly; **the export writes the short forms**
    ("Sterling Forest", "Ringwood", "Storm King"), which are exactly the
    spellings that collide with settlements. Each row prints the export's
    spelling beside its own so the gap stays visible, and a run over the real
    corpus should expect the guard to earn its place.
  - **Wikidata answers 429 under a loop.** A run without real throttling
    measures its own rate limiting. `THROTTLE_SECONDS` and `Retry-After` are
    load-bearing here, not politeness.

    python spike_hike_photo_by_name.py            the funnel, per park
    python spike_hike_photo_by_name.py --shots o/ save the lead images to look at

WHAT THIS DOES NOT DO. No fetcher, no artifact, no client change - Phase 0,
which #1450 is explicit comes before building. It measures parks, not the 385
hikes, because the hike corpus is unreachable here; **a park photograph is a
weaker claim than a hike photograph and #1450's Phase 3 is where that gets
labelled**, not here. Strategies C and D remain unmeasured.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import requests

from fetch_poi_images import MAX_PHOTO_AGE_DAYS
from lib.commons import license_allows_reuse, meta_value, parse_date_taken, strip_html
from lib.user_agent import CONTACTABLE_USER_AGENT as USER_AGENT

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

#: Wikidata answers 429 under a tight loop - #1450's own probe lost 14 of 18
#: requests to it. This is the rate that survives a run, not a courtesy.
THROTTLE_SECONDS = 1.5
RETRY_BACKOFF_SECONDS = (5, 20)
RETRYABLE_STATUSES = (429, 500, 502, 503, 504)

#: How far a Wikidata entity's own coordinate (P625) may sit from where we know
#: the place to be before it is rejected as a different thing of the same name.
#:
#: @unvalidated, but bounded by what it has to separate rather than picked from
#: nowhere: the two confusions it exists to catch are a same-named settlement
#: beside its park (kilometres) and a same-named place in another state
#: (hundreds of kilometres). 25 km sits far above the first and far below the
#: second. It must also stay LARGER than a park's own radius, because P625 for
#: a park is a single point for an area that can be 20 km across - too tight a
#: value would reject the right entity for being measured from its far corner.
#:
#: MEASURED 2026-09-15: over the ten full park names below it refused NOTHING,
#: so nothing here has tested where it sits - the one real collision found so
#: far ("Sterling Forest" -> a hamlet 300 km north) is far outside any value
#: anybody would pick. What would settle it: the distance distribution over all
#: 143 park names the export carries, in the export's own short spellings,
#: which needs the corpus this run cannot reach.
MAX_ENTITY_DRIFT_KM = 25.0

#: The thumbnail width asked of Commons - twice the card's 264 px slot, the
#: same figure fetch_poi_images.py uses and for the same reason.
IMAGE_WIDTH_PX = 640

#: The parks these hikes cluster in, with the coordinate each name is checked
#: against. Hand-drawn centres, from the same boxes spike_hike_photo_sources.py
#: measures over.
#:
#: TEN, NOT THE 143 THE EXPORT CARRIES. The Hike Finder export is behind a site
#: password here (#1468), so this is the set that could be named without it -
#: which makes every rate below a measurement over ten parks and NOT an
#: estimate of the 143. It is a probe of whether the instrument works, not of
#: how far it reaches.
#:
#: The names are spelled as a person would say them rather than as the export
#: writes them, and that difference is itself part of what #1450 flagged:
#: "Harriman-Bear Mountain State Parks" is two Wikidata entities and resolves
#: to neither, so the export's spelling needs a normalisation step this spike
#: does not build. Both spellings are carried here so the gap stays visible.
PARKS = (
    ("Harriman State Park", 41.25, -74.08, "Harriman-Bear Mountain State Parks"),
    ("Bear Mountain State Park", 41.31, -73.99, "Harriman-Bear Mountain State Parks"),
    ("Sterling Forest State Park", 41.20, -74.29, "Sterling Forest"),
    ("Norvin Green State Forest", 41.08, -74.32, "Norvin Green"),
    ("Wawayanda State Park", 41.16, -74.40, "Wawayanda"),
    ("Ringwood State Park", 41.13, -74.26, "Ringwood"),
    ("Ramapo Mountain State Forest", 41.02, -74.21, "Ramapo Mountain"),
    ("Black Rock Forest", 41.42, -74.01, "Black Rock Forest"),
    ("Storm King State Park", 41.43, -73.97, "Storm King"),
    ("Catskill Park", 42.05, -74.30, "Catskill Park"),
)

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class Entity:
    """A Wikidata item a name resolved to, and whether it is believed."""

    qid: str
    label: str
    description: str
    lat: float | None
    lon: float | None
    drift_km: float | None
    accepted: bool
    rejected_because: str | None


@dataclass(frozen=True)
class LeadImage:
    """A P18 lead image with everything needed to judge and to credit it."""

    entity: Entity
    filename: str
    thumb_url: str | None
    page_url: str
    licence: str
    author: str | None
    taken: date | None

    @property
    def licence_ok(self) -> bool:
        return license_allows_reuse(self.licence)

    @property
    def creditable(self) -> bool:
        """CC BY and CC BY-SA require naming the author; PD and CC0 do not.
        The same rule lib/commons.eligible_photo applies, restated for a
        record that did not come from a geosearch hit."""
        if not self.licence.lower().startswith("cc-by"):
            return True
        return bool(self.author)

    def fresh(self, cutoff: date) -> bool:
        return self.taken is not None and self.taken >= cutoff


def kilometres_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle km. Local rather than imported because lib/hikefinder's
    metres_between is about a hiker's track and this is about whether two
    databases mean the same place - different question, different units."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def session() -> requests.Session:
    made = requests.Session()
    made.headers["User-Agent"] = USER_AGENT
    return made


def api_get(made: requests.Session, url: str, params: dict) -> dict:
    """One throttled, retried API call returning decoded JSON.

    `Retry-After` is honoured where the server sends one, because Wikimedia's
    API etiquette asks for exactly that and this spike exists partly because
    #1450's probe did not. A non-retryable status raises rather than returning
    empty: a run that counted a 429 as "this park has no photograph" would
    report the rate limiter's opinion as a finding about the world.
    """
    full = {**params, "format": "json"}
    for attempt, delay in enumerate((*RETRY_BACKOFF_SECONDS, None)):
        try:
            response = made.get(url, params=full, timeout=60)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
            if delay is None:
                raise
            print(f"    {type(error).__name__} on attempt {attempt + 1}, retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
            continue
        if response.status_code in RETRYABLE_STATUSES and delay is not None:
            wait = delay
            header = response.headers.get("Retry-After")
            if header and header.isdigit():
                wait = max(wait, int(header))
            print(f"    {response.status_code} on attempt {attempt + 1}, retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        response.raise_for_status()
        payload = response.json()
        time.sleep(THROTTLE_SECONDS)
        return payload
    raise AssertionError("unreachable")


def resolve(made: requests.Session, name: str, lat: float, lon: float, limit: int = 5) -> Entity | None:
    """The Wikidata item `name` means AT THIS PLACE, or None.

    Candidates are searched by name and then made to prove themselves against
    the coordinate: the first hit is routinely a different thing of the same
    name, and "Sterling Forest" - a hamlet, not the state park the hikes are
    in - is the case that motivated this. A name that resolves only to a
    distant entity comes back as that entity marked `accepted=False`, so the
    report can distinguish "no such item" from "an item we refused", which are
    different problems with different fixes.
    """
    found = api_get(
        made,
        WIKIDATA_API,
        {"action": "wbsearchentities", "search": name, "language": "en", "type": "item", "limit": limit},
    ).get("search", [])
    if not found:
        return None

    qids = [hit["id"] for hit in found]
    entities = api_get(
        made,
        WIKIDATA_API,
        {"action": "wbgetentities", "ids": "|".join(qids), "props": "claims|descriptions|labels", "languages": "en"},
    ).get("entities", {})

    best: Entity | None = None
    for qid in qids:  # search order is relevance order; keep it
        entity = entities.get(qid) or {}
        claims = entity.get("claims") or {}
        description = ((entity.get("descriptions") or {}).get("en") or {}).get("value", "")
        label = ((entity.get("labels") or {}).get("en") or {}).get("value", qid)

        coordinate = (claims.get("P625") or [{}])[0].get("mainsnak", {}).get("datavalue", {}).get("value")
        if not coordinate:
            candidate = Entity(qid, label, description, None, None, None, False, "no coordinate to check")
        else:
            elat, elon = float(coordinate["latitude"]), float(coordinate["longitude"])
            drift = kilometres_between((lat, lon), (elat, elon))
            if drift <= MAX_ENTITY_DRIFT_KM:
                return Entity(qid, label, description, elat, elon, drift, True, None)
            candidate = Entity(qid, label, description, elat, elon, drift, False, f"{drift:.0f} km away")

        if best is None:
            best = candidate
    return best


def lead_image(made: requests.Session, entity: Entity) -> LeadImage | None:
    """The entity's P18 with its Commons licence, author and capture date, or
    None when it carries no lead image at all."""
    claims = (
        api_get(made, WIKIDATA_API, {"action": "wbgetentities", "ids": entity.qid, "props": "claims"})
        .get("entities", {})
        .get(entity.qid, {})
        .get("claims", {})
    )
    statements = claims.get("P18")
    if not statements:
        return None
    filename = statements[0]["mainsnak"]["datavalue"]["value"]

    info = api_get(
        made,
        COMMONS_API,
        {
            "action": "query",
            "prop": "imageinfo",
            "titles": f"File:{filename}",
            "iiprop": "url|mime|extmetadata",
            "iiurlwidth": str(IMAGE_WIDTH_PX),
            "iiextmetadatafilter": "DateTimeOriginal|License|LicenseShortName|Artist|Attribution",
        },
    )
    pages = ((info.get("query") or {}).get("pages") or {}).values()
    for page in pages:
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        first = infos[0]
        extmetadata = first.get("extmetadata") or {}
        author = strip_html(meta_value(extmetadata, "Attribution") or meta_value(extmetadata, "Artist"))
        return LeadImage(
            entity=entity,
            filename=filename,
            thumb_url=first.get("thumburl"),
            page_url=first.get("descriptionurl") or "",
            licence=meta_value(extmetadata, "License"),
            author=author or None,
            taken=parse_date_taken(meta_value(extmetadata, "DateTimeOriginal")),
        )
    return None


def save_shot(made: requests.Session, image: LeadImage, directory: Path) -> Path | None:
    """The lead image onto disk, so a person can see what P18 actually chose.

    #1450's standard: the headline number is what a person confirms, "not what
    the filters admit". A P18 is a human's pick, which makes it far likelier to
    depict its subject than a geosearch hit - but "Bear Mountain State Park"
    leads with a photograph of a bridge, so likelier is not the same as true.
    """
    if not image.thumb_url:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "_" for c in image.entity.label)[:40]
    target = directory / f"{slug}.jpg"
    try:
        response = made.get(image.thumb_url, timeout=60)
        response.raise_for_status()
        target.write_bytes(response.content)
    except requests.exceptions.RequestException as error:
        print(f"    could not save {image.filename}: {error}", file=sys.stderr)
        return None
    return target


def report(made: requests.Session, shots: Path | None, today: date | None = None) -> int:
    cutoff = (today or date.today()) - timedelta(days=MAX_PHOTO_AGE_DAYS)

    resolved: list[Entity] = []
    rejected: list[Entity] = []
    missing: list[str] = []
    images: list[LeadImage] = []
    no_image: list[Entity] = []

    print()
    print("A NAME, RESOLVED TO A PLACE, AND THE PICTURE SOMEBODY CHOSE FOR IT")
    print(f"Wikidata P18 over {len(PARKS)} parks; an entity must sit within {MAX_ENTITY_DRIFT_KM:.0f} km to be believed.")
    print()

    for name, lat, lon, export_spelling in PARKS:
        entity = resolve(made, name, lat, lon)
        if entity is None:
            missing.append(name)
            print(f"  {name:<32} NO WIKIDATA ITEM")
            continue
        if not entity.accepted:
            rejected.append(entity)
            print(f"  {name:<32} REFUSED {entity.qid} ({entity.rejected_because}) - {entity.description[:38]}")
            continue

        resolved.append(entity)
        image = lead_image(made, entity)
        if image is None:
            no_image.append(entity)
            print(f"  {name:<32} {entity.qid:<10} no P18")
            continue

        images.append(image)
        age = "no date" if image.taken is None else image.taken.isoformat()
        verdict = "FRESH" if image.fresh(cutoff) else "stale"
        licence = image.licence or "(none)"
        print(f"  {name:<32} {entity.qid:<10} {image.filename[:34]:<34} {licence:<13} {age:<11} {verdict}")
        if shots:
            save_shot(made, image, shots)
        if export_spelling != name:
            print(f"  {'':<32} (the export writes this park '{export_spelling}')")

    shippable = [i for i in images if i.licence_ok and i.creditable]
    fresh = [i for i in shippable if i.fresh(cutoff)]

    print()
    print("  THE FUNNEL")
    print(f"    park names asked                  {len(PARKS):>3}")
    print(f"    resolved to a Wikidata entity     {len(resolved) + len(rejected):>3}")
    print(f"    ...that is actually that place    {len(resolved):>3}   ({len(rejected)} refused on distance)")
    print(f"    carrying a P18 lead image         {len(images):>3}")
    print(f"    ...whose licence we may ship      {len(shippable):>3}")
    print(f"    ...inside the {MAX_PHOTO_AGE_DAYS // 365}-year freshness bar   {len(fresh):>3}")
    print()
    print("  WHAT THE FRESHNESS BAR COSTS, which is the number this spike exists to show:")
    print(f"    shippable ignoring freshness      {len(shippable):>3}  of {len(PARKS)} parks")
    print(f"    shippable as the bar stands today {len(fresh):>3}  of {len(PARKS)} parks")
    print()
    print("  fetch_poi_images.py says the bar 'moves when the measured coverage says it")
    print("  should'. features/POI_PHOTOS.md already owes this decision to the ATC")
    print("  inventory photos (2007-2017, all of them past it). A landscape is the third")
    print("  case and the easiest to argue: a ridge does not dry up like a spring.")
    print("  NOTHING HERE DECIDES IT - that is a maintainer's call.")
    print()
    print("  AND A PHOTOGRAPH OF A PARK IS NOT A PHOTOGRAPH OF A HIKE. #1450's Phase 3")
    print("  is where that gets labelled (`photoSubject`), and it is not optional polish:")
    print("  'never let a display outrun its source'.")
    if shots:
        print()
        print(f"  Lead images saved to {shots} - look at them before believing any of the above.")
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shots", type=Path, default=None, help="Directory to save each lead image into.")
    args = parser.parse_args(argv)
    return report(session(), args.shots)


if __name__ == "__main__":
    raise SystemExit(run())
