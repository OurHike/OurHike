"""Spike: can a geo-searchable photo corpus illustrate the 385 NYNJTC hikes?

This is **strategy E** for #1450 - "Find a photograph for each of the 385
NYNJTC hikes, using the names in their prose rather than a radius around their
trailhead" - and that issue's plan does not list it. Strategies A-D there are
all Wikimedia-family: a curated Wikidata lead image, a Commons category, a
Commons text search, a Commons geosearch along the corridor. This measures the
three OTHER corpora that answer a lat/long query - **Panoramax**, **Mapillary**
and **iNaturalist** - because "is there an open photo library we can search by
coordinate" is the question that gets asked first every time this comes up, and
until now the answer in this repository was an inference rather than a count.

MEASURED 2026-09-15, over hand-drawn boxes around the ten parks the export's
hikes cluster in. Two numbers per source: images returned, and the DISTINCT
LOCATIONS they sit at.

    source        images   distinct spots   every park covered?
    panoramax      1,081              808   no - 4 of 10 hold nothing at all
    inaturalist   41,428                -   yes, every one
    mapillary          -                -   unmeasured, needs a token

THE TWO SOURCES FAIL IN OPPOSITE DIRECTIONS, and that is the finding.

**Panoramax has the right shape and no data.** A street-level image is a
photograph taken by somebody standing on the ground, which is exactly the
subject-matching problem Commons could not solve - the photographer's route IS
the answer to "what is this a photograph of". But the corpus is not there:
Harriman/Bear Mountain, which carries more of these hikes than any other park,
holds **2 images at 1 spot**; Norvin Green, Wawayanda, Ringwood and Ramapo
Mountain hold **nothing at all**. Where the counts are high they are high for a
reason that disqualifies them - the Palisades' 1,000+ images are 793 spots of
one contributor's **dashcam**, the Interstate Parkway shot through a windscreen
with the car's hood in frame. Sterling Forest's 73 images are **9 spots from
one person on one day**, and one of the frames is a pile of storm deadfall.
**Street-level imagery follows streets**, and these hikes are chosen for being
where vehicles are not.

**iNaturalist has the data and the wrong subject.** 41,428 openly-licensed
observations across the same ten parks, every park covered, four figures even
in the ones Panoramax cannot see at all. It is the best-covered geo-searchable
photo corpus this project has measured, by a factor of about forty. And every
photograph in it is framed on an organism: a plain random sample from Harriman
returned six macro shots of leaves against leaf litter, shot downward at the
ground. Not one showed a trail, a ridge or a view.

**So iNaturalist is the most dangerous of the three, not the best.** It is the
source that would make this feature look finished - wire it in and all 385
hikes get a picture, every one of them a leaf. features/POI_PHOTOS.md already
paid for this lesson once without naming the source: 35 of the 76 Commons hits
in the 2026-08-08 measurement were iNaturalist uploads reaching Commons, and
the card for Gravel Springs Hut Shelter would have shown an Asiatic dayflower.
That was not Commons failing to filter. That was iNaturalist working exactly as
designed, through a pipe nobody had looked down.

A LICENCE TRAP WORTH THE SAME WARNING spike_flickr_group.py GAVE. Flickr's
licence *names* carry no version, so a measurement reading the name would count
the whole CC 2.0 suite as shippable. **iNaturalist has the identical problem in
a different field**: its API returns `license_code: "cc-by"` and an attribution
string reading "(CC BY)", with no version anywhere in either. `lib/commons.py`
rejects both, correctly - it cannot verify a floor of 4.0 against a licence that
does not state its version. Shipping iNaturalist photos would mean ASSERTING the
version from platform policy rather than reading it per photo, which is a
materially weaker claim than Commons' machine-readable `extmetadata`, and one
this file will not make on the project's behalf.

WHAT THIS DOES NOT DO. No fetcher, no artifact, no client change - Phase 0 of
#1450's plan, which is explicit that measuring comes before building. It does
not touch strategies A-D and cannot call that issue's 25% kill criterion, which
is about all strategies together.

    python spike_hike_photo_sources.py              per hike, needs the cache
    python spike_hike_photo_sources.py --regional   per park, needs nothing
    python spike_hike_photo_sources.py --shots out/ save thumbnails to look at

TWO MODES, BECAUSE THE CORPUS IS NOT ALWAYS REACHABLE. The per-hike mode reads
`data/raw/hikefinder.json` and answers #1450's actual question - how many of the
385 get a candidate. The `--regional` mode needs no corpus and asks the cheaper
question that comes first: is there ANY openly-licensed imagery in the geography
these hikes live in? A park holding the busiest hikes in the network and two
photographs answers strategy E without any join being attempted, and it is the
mode that runs where the export's site password is not set (#1468).

COUNTING LOCATIONS, NOT IMAGES. Sterling Forest returns 73 images, which reads
like coverage, from nine spots. An image count answers "how much did somebody
upload"; a location count answers "how many places can be photographed", and
only the second bears on whether 385 hikes can have pictures.

LOOK AT THE PICTURES. #1450 is explicit that the headline number must be what a
person confirms, "not what the filters admit" - the dayflower cleared every
automatic bar. Every verdict above rests on opening thumbnails, which is what
`--shots` is for, and none of it could have been reached from the counts alone.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from lib.commons import license_allows_reuse
from lib.hikefinder import metres_between, parse_gpx
from lib.user_agent import CONTACTABLE_USER_AGENT as USER_AGENT

ROOT = Path(__file__).parent
CACHE_PATH = ROOT / "data" / "raw" / "hikefinder.json"
GPX_DIR = ROOT / "data" / "raw" / "hikefinder_gpx"

PANORAMAX_API = "https://api.panoramax.xyz/api/search"
MAPILLARY_API = "https://graph.mapillary.com/images"
INATURALIST_API = "https://api.inaturalist.org/v1/observations"

#: Mapillary's API needs an OAuth token even for public reads; without one it
#: answers 500 rather than 401, which is worth knowing before concluding the
#: source is empty. Absent is a SUPPORTED state here, not a misconfiguration -
#: the run says so and reports the other two, the same posture
#: fetch_hikefinder.py takes toward its site password.
MAPILLARY_TOKEN_ENV = "MAPILLARY_ACCESS_TOKEN"

#: Every Mapillary image is CC BY-SA 4.0 under their uploader terms, and the
#: images endpoint returns no per-image licence field to read instead. So this
#: is asserted from the platform's terms rather than measured per file, which is
#: a weaker claim than Panoramax's per-image `license` and is labelled as one
#: wherever it is printed.
MAPILLARY_ASSUMED_LICENCE = "cc-by-sa-4.0"

#: Which iNaturalist photo licences to ask for. These are the open ones in
#: iNaturalist's vocabulary, and they are spelled WITHOUT A VERSION because
#: that is the only spelling its API accepts or returns - see the module
#: docstring's licence-trap note. They are sent as a filter, never treated as
#: a verdict: what comes back still goes through `lib.commons` like everything
#: else, and is rejected by it, which is the honest outcome rather than a bug
#: to route around.
INATURALIST_OPEN_LICENCES = ("cc0", "cc-by", "cc-by-sa")

#: How far from a hike's start, or from a point on its drawn track, an image
#: may sit and still be a candidate photograph of that hike.
#:
#: @unvalidated. Picked as roughly the distance over which a photograph still
#: shows recognisably the same place on a wooded trail - far enough to catch a
#: frame taken a bend earlier, close enough that it is not the next valley.
#: Nobody has checked it, and on this measurement it does not decide anything:
#: Panoramax is empty at any radius this side of a kilometre, and iNaturalist
#: is dense enough that every hike clears any threshold while still failing on
#: subject. What would settle it is the first source that has images along
#: these trails that are ALSO of them - then the question becomes real and
#: wants a person looking at frames at 100 m, 250 m and 500 m and saying which
#: still depict the walk.
NEAR_METRES = 250.0

#: How finely a drawn GPX track is sampled before asking each sample for
#: imagery. 400 m matches the sampling export_suggested_hikes.py already uses
#: when checking that a re-route reproduces a published track, so the two walk
#: the same line the same way rather than measuring their own arithmetic.
TRACK_SAMPLE_METRES = 400.0

#: Sequential and throttled - a spike making a few hundred read requests
#: against three public APIs that owe this project nothing. iNaturalist's
#: documented courtesy limit is 60 requests a minute and it asks callers to
#: keep well under it, which this does.
THROTTLE_SECONDS = 1.0
RETRY_BACKOFF_SECONDS = (5, 20)
RETRYABLE_STATUSES = (429, 500, 502, 503, 504)

#: Hand-drawn boxes around the parks the export's hikes cluster in, generous
#: rather than tight. GENEROUS IS THE CONSERVATIVE DIRECTION for a kill
#: decision: an overestimate of coverage that still comes back empty is a
#: stronger result than a tight box that might have clipped the imagery.
#:
#: The two controls are not padding. A row of zeroes is also what a broken
#: bbox, a swapped axis order or a dead endpoint looks like, and the Panoramax
#: column is mostly going to print zeroes - so this has to be able to tell its
#: readers that the zeroes are the source's. Paris is Panoramax's home
#: geography and Manhattan is the dense US city nearest these parks.
PARK_BOXES = (
    ("Harriman / Bear Mountain SP", -74.20, 41.15, -73.95, 41.35),
    ("Sterling Forest SP", -74.38, 41.13, -74.20, 41.27),
    ("Norvin Green SF", -74.40, 41.03, -74.25, 41.13),
    ("Wawayanda SP", -74.48, 41.10, -74.33, 41.22),
    ("Ringwood SP", -74.32, 41.08, -74.20, 41.18),
    ("Ramapo Mountain SF", -74.28, 40.97, -74.15, 41.08),
    ("Black Rock Forest", -74.06, 41.38, -73.96, 41.46),
    ("Storm King SP", -74.00, 41.41, -73.93, 41.46),
    ("Catskill Park (S half)", -74.50, 41.90, -74.05, 42.20),
    ("Palisades (NJ section)", -73.96, 40.85, -73.88, 41.02),
    ("CONTROL Paris", 2.25, 48.82, 2.42, 48.90),
    ("CONTROL Manhattan", -74.02, 40.70, -73.93, 40.80),
)

#: Distinct-location rounding, in decimal places of latitude and longitude.
#: 4dp is about 11 m at these latitudes - inside one stride, so two frames that
#: round together were taken from the same spot by any reading a hiker would
#: recognise.
LOCATION_DECIMALS = 4

PAGE_LIMIT = 1000


@dataclass(frozen=True)
class Image:
    """One candidate photograph from any of the three sources.

    `licence_measured` says whether the licence was read per image or asserted
    from the platform's terms - the difference between Panoramax's per-image
    field and Mapillary's blanket one, and a difference #1450's licence
    constraints turn on.

    `subject` is what the SOURCE says the photograph is of, where it says
    anything. Only iNaturalist does, and what it says is the finding: a taxon
    name, every time, because that is what an observation is.
    """

    source: str
    image_id: str
    lat: float
    lon: float
    captured: str | None
    licence: str
    licence_measured: bool
    producer: str | None
    thumbnail: str | None
    subject: str | None = None

    @property
    def shippable(self) -> bool:
        """Whether OurHike's existing licence gate would let this ship. The
        same `lib.commons.license_allows_reuse` the Commons fetch gates on, so
        a change in that policy moves this measurement with it rather than
        leaving a second copy of the rule here to drift."""
        return license_allows_reuse(self.licence)

    @property
    def location_key(self) -> tuple[float, float]:
        return (round(self.lat, LOCATION_DECIMALS), round(self.lon, LOCATION_DECIMALS))


def session() -> requests.Session:
    """One session for the whole run, naming the project in its User-Agent -
    the shape every fetcher here uses (lib/user_agent.py)."""
    made = requests.Session()
    made.headers["User-Agent"] = USER_AGENT
    return made


def _get(made: requests.Session, url: str, params: dict, headers: dict[str, str] | None = None) -> dict:
    """One throttled, retried GET returning decoded JSON.

    Transient faults get another try; a non-retryable status raises. A spike
    that quietly counted a failed request as "no images" would manufacture
    exactly the finding it is here to test, which is the one mistake this
    measurement cannot afford to make - so there is no `except` here that
    returns an empty list.
    """
    for attempt, delay in enumerate((*RETRY_BACKOFF_SECONDS, None)):
        try:
            response = made.get(url, params=params, headers=headers or {}, timeout=90)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
            if delay is None:
                raise
            print(f"    {type(error).__name__} on attempt {attempt + 1}, retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
            continue
        if response.status_code in RETRYABLE_STATUSES and delay is not None:
            print(f"    {response.status_code} on attempt {attempt + 1}, retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
            continue
        response.raise_for_status()
        payload = response.json()
        time.sleep(THROTTLE_SECONDS)
        return payload
    raise AssertionError("unreachable")


def panoramax_in_box(made: requests.Session, bbox: tuple[float, float, float, float], limit: int = PAGE_LIMIT) -> list[Image]:
    """Every Panoramax image in a bbox, as far as one page reaches.

    One page rather than following `next` links: this measures whether a place
    has imagery at all, and a park that needs pagination to prove it has some
    has already answered the question.
    """
    payload = _get(made, PANORAMAX_API, {"bbox": ",".join(str(v) for v in bbox), "limit": limit})
    images = []
    for feature in payload.get("features", []):
        properties = feature.get("properties") or {}
        box = feature.get("bbox") or []
        if len(box) < 2:
            continue
        images.append(
            Image(
                source="panoramax",
                image_id=str(feature.get("id", "")),
                lon=float(box[0]),
                lat=float(box[1]),
                captured=(properties.get("datetime") or None),
                licence=str(properties.get("license") or ""),
                licence_measured=True,
                producer=properties.get("geovisio:producer"),
                thumbnail=properties.get("geovisio:thumbnail"),
            )
        )
    return images


def mapillary_in_box(
    made: requests.Session, bbox: tuple[float, float, float, float], token: str, limit: int = PAGE_LIMIT
) -> list[Image]:
    """Every Mapillary image in a bbox, as far as one page reaches.

    The licence is not read per image because the endpoint does not serve one;
    see MAPILLARY_ASSUMED_LICENCE for what is asserted instead and on what
    basis.
    """
    payload = _get(
        made,
        MAPILLARY_API,
        {
            "bbox": ",".join(str(v) for v in bbox),
            "limit": limit,
            "fields": "id,computed_geometry,geometry,captured_at,thumb_1024_url",
        },
        {"Authorization": f"OAuth {token}"},
    )
    images = []
    for entry in payload.get("data", []):
        geometry = entry.get("computed_geometry") or entry.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            continue
        images.append(
            Image(
                source="mapillary",
                image_id=str(entry.get("id", "")),
                lon=float(coordinates[0]),
                lat=float(coordinates[1]),
                captured=str(entry.get("captured_at")) if entry.get("captured_at") else None,
                licence=MAPILLARY_ASSUMED_LICENCE,
                licence_measured=False,
                producer=None,
                thumbnail=entry.get("thumb_1024_url"),
            )
        )
    return images


def inaturalist_in_box(made: requests.Session, bbox: tuple[float, float, float, float], limit: int = 200) -> list[Image]:
    """Openly-licensed iNaturalist observations in a bbox, as photographs.

    `subject` carries the taxon, and it is the single most useful field this
    spike collects: it is the source telling you, in its own words, that the
    photograph is of a plant. No other corpus here volunteers what its images
    depict, and the whole difficulty of #1450 is that nothing else can.
    """
    west, south, east, north = bbox
    payload = _get(
        made,
        INATURALIST_API,
        {
            "swlng": west,
            "swlat": south,
            "nelng": east,
            "nelat": north,
            "photo_license": ",".join(INATURALIST_OPEN_LICENCES),
            "per_page": min(limit, 200),
        },
    )
    images = []
    for observation in payload.get("results", []):
        photos = observation.get("photos") or []
        if not photos:
            continue
        photo = photos[0]
        location = observation.get("geojson") or {}
        coordinates = location.get("coordinates") or []
        if len(coordinates) < 2:
            continue
        taxon = observation.get("taxon") or {}
        images.append(
            Image(
                source="inaturalist",
                image_id=str(photo.get("id", "")),
                lon=float(coordinates[0]),
                lat=float(coordinates[1]),
                captured=observation.get("observed_on"),
                # Versionless, and deliberately not repaired here - see the
                # module docstring. lib/commons.py rejects it, which is the
                # honest answer rather than a bug to route around.
                licence=str(photo.get("license_code") or ""),
                licence_measured=True,
                producer=(observation.get("user") or {}).get("login"),
                thumbnail=(photo.get("url") or "").replace("/square.", "/medium.") or None,
                subject=taxon.get("name"),
            )
        )
    return images


def inaturalist_count(made: requests.Session, bbox: tuple[float, float, float, float]) -> int:
    """How many openly-licensed observations a box holds, without paging them.

    `per_page=0` returns `total_results` alone, which is the whole coverage
    question for a few bytes - iNaturalist's boxes run to five figures and
    paging them to count them would be rude as well as slow.
    """
    west, south, east, north = bbox
    payload = _get(
        made,
        INATURALIST_API,
        {
            "swlng": west,
            "swlat": south,
            "nelng": east,
            "nelat": north,
            "photo_license": ",".join(INATURALIST_OPEN_LICENCES),
            "per_page": 0,
        },
    )
    return int(payload.get("total_results") or 0)


def box_around(lat: float, lon: float, metres: float) -> tuple[float, float, float, float]:
    """A bbox of roughly `metres` either side of a point.

    Latitude degrees are ~111,320 m everywhere; longitude degrees shrink by
    cos(latitude), and at 41 N that is a 25% difference which a square box in
    degrees would get wrong.
    """
    delta_lat = metres / 111_320.0
    delta_lon = metres / (111_320.0 * math.cos(math.radians(lat)))
    return (lon - delta_lon, lat - delta_lat, lon + delta_lon, lat + delta_lat)


def sample_track(points: list, every_metres: float) -> list[tuple[float, float]]:
    """Points along a drawn track, no closer together than `every_metres`.

    Keeps the first and last regardless, so a track shorter than one sample
    still asks about both of its ends rather than about nothing.
    """
    if not points:
        return []
    kept = [(points[0].lat, points[0].lon)]
    for point in points[1:]:
        if metres_between(kept[-1], (point.lat, point.lon)) >= every_metres:
            kept.append((point.lat, point.lon))
    last = (points[-1].lat, points[-1].lon)
    if kept[-1] != last:
        kept.append(last)
    return kept


def summarise(images: list[Image]) -> dict:
    """Counts that distinguish "somebody uploaded a lot" from "a lot of places
    can be photographed" - see the module docstring on Sterling Forest."""
    shippable = [image for image in images if image.shippable]
    licences: dict[str, int] = {}
    for image in images:
        key = image.licence or "(none stated)"
        licences[key] = licences.get(key, 0) + 1
    return {
        "images": len(images),
        "locations": len({image.location_key for image in images}),
        "shippable_images": len(shippable),
        "shippable_locations": len({image.location_key for image in shippable}),
        "producers": len({image.producer for image in images if image.producer}),
        "subjects": len({image.subject for image in images if image.subject}),
        "licences": licences,
    }


def save_shots(made: requests.Session, images: list[Image], directory: Path, label: str, how_many: int) -> int:
    """Thumbnails onto disk so a person can look at what the filters admitted.

    #1450 is explicit that the headline number must be what a person confirms,
    "not what the filters admit" - the dayflower cleared every automatic bar. A
    count of images in a park is not evidence that any of them photograph a
    hike, and the only way to find that out is to open them. Every verdict in
    this module's docstring came from doing so.
    """
    directory.mkdir(parents=True, exist_ok=True)
    saved = 0
    seen: set[tuple[float, float]] = set()
    for image in images:
        if saved >= how_many:
            break
        if not image.thumbnail or image.location_key in seen:
            continue
        seen.add(image.location_key)
        slug = "".join(c if c.isalnum() else "_" for c in f"{image.source}_{label}")[:48]
        target = directory / f"{slug}_{saved}_{image.lat:.5f}_{image.lon:.5f}.jpg"
        try:
            response = made.get(image.thumbnail, timeout=60)
            response.raise_for_status()
            target.write_bytes(response.content)
        except requests.exceptions.RequestException as error:
            print(f"    thumbnail failed for {image.image_id}: {error}", file=sys.stderr)
            continue
        saved += 1
    return saved


def gather(made: requests.Session, bbox: tuple[float, float, float, float], token: str | None, limit: int) -> list[Image]:
    """Every source's answer for one box, with a dead source reported rather
    than silently contributing nothing."""
    found: list[Image] = []
    for name, call in (
        ("panoramax", lambda: panoramax_in_box(made, bbox, limit)),
        ("inaturalist", lambda: inaturalist_in_box(made, bbox, min(limit, 200))),
        *((("mapillary", lambda: mapillary_in_box(made, bbox, token, limit)),) if token else ()),
    ):
        try:
            found.extend(call())
        except Exception as error:  # one dead source must not lose the others
            print(f"    {name}: {type(error).__name__}: {error}", file=sys.stderr)
    return found


def report_regional(made: requests.Session, token: str | None, shots: Path | None, shots_per_area: int) -> int:
    """Coverage over the parks, needing no hike corpus."""
    print()
    print("OPENLY-LICENSED PHOTO CORPORA OVER THE NYNJTC PARKS")
    print("Boxes are hand-drawn and generous; CONTROL rows prove a zero is the source's.")
    print()
    header = f"  {'area':<30} {'pano':>6} {'spots':>6} {'who':>4} {'iNat obs':>10} {'taxa':>6}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for name, *bbox in PARK_BOXES:
        box = (bbox[0], bbox[1], bbox[2], bbox[3])

        panoramax: list[Image] = []
        try:
            panoramax = panoramax_in_box(made, box)
        except Exception as error:
            print(f"  {name:<30} panoramax ERROR {type(error).__name__}: {error}")
        if token:
            try:
                panoramax.extend(mapillary_in_box(made, box, token))
            except Exception as error:
                print(f"  {name:<30} mapillary ERROR {type(error).__name__}: {error}")

        try:
            observations = inaturalist_count(made, box)
        except Exception as error:
            print(f"  {name:<30} inaturalist ERROR {type(error).__name__}: {error}")
            observations = -1

        sample: list[Image] = []
        try:
            sample = inaturalist_in_box(made, box, limit=50)
        except Exception as error:
            print(f"  {name:<30} inaturalist sample ERROR {type(error).__name__}: {error}")

        stats = summarise(panoramax)
        taxa = summarise(sample)["subjects"]
        flag = "   <- no street-level imagery" if not stats["images"] else ""
        print(
            f"  {name:<30} {stats['images']:>6} {stats['locations']:>6} {stats['producers']:>4} "
            f"{observations:>10,} {taxa:>6}{flag}"
        )
        if shots:
            for group in (panoramax, sample):
                if group:
                    save_shots(made, group, shots, name, shots_per_area)

    print()
    print(f"  pano   street-level images returned (one page, limit {PAGE_LIMIT}); with mapillary")
    print("         folded in when a token is set")
    print(f"  spots  distinct locations at {LOCATION_DECIMALS}dp (~11 m) - THE COLUMN TO READ, because")
    print("         images count what somebody uploaded and spots count how many places")
    print("         can be photographed")
    print("  who    distinct contributors - one hobbyist's afternoon is not a corpus")
    print("  iNat   openly-licensed observations, and the distinct taxa in a 50-row sample")
    print()
    print("  iNATURALIST'S COLUMN IS NOT GOOD NEWS. Every one of those observations is")
    print("  framed on an organism, which is what the taxa column is there to show. It is")
    print("  the source that would make this feature look finished and leave 385 hikes")
    print("  illustrated by leaves - see the module docstring.")
    return 0


def report_per_hike(made: requests.Session, token: str | None, shots: Path | None, limit: int | None) -> int:
    """#1450's actual question: how many of the 385 hikes get a candidate."""
    if not CACHE_PATH.exists():
        print(f"Missing {CACHE_PATH} - run fetch_hikefinder.py first.")
        print()
        print("If that fetch cannot reach the export (it answers 200 with a 'Site Password")
        print("Required' page unless HIKEFINDER_PASSWORD is set, #1468), use --regional,")
        print("which needs no corpus and answers whether these parks hold imagery at all.")
        return 1

    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")).get("hikes") or {}
    if not cache:
        print(f"{CACHE_PATH} holds no hikes - nothing to measure.")
        return 1

    keys = sorted(cache, key=lambda k: int(k))
    if limit is not None:
        keys = keys[:limit]

    print()
    print(f"PHOTO CANDIDATES PER HIKE - {len(keys)} hikes")
    print(f"start point and drawn track, {NEAR_METRES:.0f} m radius, sampled every {TRACK_SAMPLE_METRES:.0f} m")
    print()

    with_street_level = 0
    with_shippable = 0
    with_inaturalist = 0
    without_coords = 0
    rows: list[tuple[str, int, int, int]] = []

    for key in keys:
        hike = cache[key]
        name = hike.get("name") or f"hike {key}"
        probes: list[tuple[float, float]] = []

        start = hike.get("start") or {}
        if start.get("lat") is not None and start.get("lon") is not None:
            probes.append((float(start["lat"]), float(start["lon"])))

        gpx_name = hike.get("gpx_file")
        if gpx_name:
            gpx_path = GPX_DIR / gpx_name
            if gpx_path.exists():
                track = parse_gpx(gpx_path.read_text(encoding="utf-8"))
                if track and track.points:
                    probes.extend(sample_track(track.points, TRACK_SAMPLE_METRES))

        if not probes:
            without_coords += 1
            continue

        found: list[Image] = []
        for lat, lon in probes:
            found.extend(gather(made, box_around(lat, lon, NEAR_METRES), token, 100))

        unique = list({(image.source, image.image_id): image for image in found}.values())
        street = [image for image in unique if image.source in ("panoramax", "mapillary")]
        nature = [image for image in unique if image.source == "inaturalist"]

        if street:
            with_street_level += 1
        if nature:
            with_inaturalist += 1
        shippable = [image for image in unique if image.shippable]
        if shippable:
            with_shippable += 1
        if street or nature:
            rows.append((name, len(street), len(nature), len(shippable)))
        if shots and street:
            save_shots(made, street, shots, name, 2)

    measured = len(keys) - without_coords

    def share(count: int) -> str:
        return f"  ({count / measured:.1%})" if measured else ""

    print(f"  hikes probed                       {measured}")
    print(f"  no coordinates to probe            {without_coords}")
    print(f"  with a STREET-LEVEL image nearby   {with_street_level}{share(with_street_level)}")
    print(f"  with an iNATURALIST photo nearby   {with_inaturalist}{share(with_inaturalist)}")
    print(f"  with anything the LICENCE allows   {with_shippable}{share(with_shippable)}")
    print()
    if rows:
        print(f"  {'hike':<46} {'street':>7} {'iNat':>6} {'ship':>6}")
        for name, street, nature, shippable in sorted(rows, key=lambda r: -r[1])[:40]:
            print(f"  {name[:46]:<46} {street:>7} {nature:>6} {shippable:>6}")
        print()
    print("  A CANDIDATE IS NOT A PHOTOGRAPH OF THE HIKE, and the iNaturalist column is")
    print("  the proof: it will be high for nearly every hike, and every one of those")
    print("  photographs is of a plant. #1450's bar is what a person confirms; --shots")
    print("  writes thumbnails so somebody can actually look.")
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--regional",
        action="store_true",
        help="Measure coverage over the parks rather than per hike; needs no cache.",
    )
    parser.add_argument("--shots", type=Path, default=None, help="Directory to save thumbnails into, to look at.")
    parser.add_argument("--shots-per-area", type=int, default=3, help="How many thumbnails per park (--regional).")
    parser.add_argument("--limit", type=int, default=None, help="Probe only the first N hikes.")
    args = parser.parse_args(argv)

    token = os.environ.get(MAPILLARY_TOKEN_ENV)
    if token:
        print(f"mapillary: {MAPILLARY_TOKEN_ENV} is set, all three sources measured")
    else:
        print(f"mapillary: no {MAPILLARY_TOKEN_ENV} set, so PANORAMAX AND INATURALIST ONLY.")
        print("           Mapillary answers 500 rather than 401 without one, so an unset")
        print("           token looks exactly like a dead endpoint. It is the largest of")
        print("           the street-level corpora and nothing here is evidence about it.")

    made = session()
    if args.regional:
        return report_regional(made, token, args.shots, args.shots_per_area)
    return report_per_hike(made, token, args.shots, args.limit)


if __name__ == "__main__":
    raise SystemExit(run())
