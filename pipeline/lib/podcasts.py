"""Podcast episodes picked for a hike, checked and shaped for the phone (#1683).

reference/podcast_episodes.json is the judgement - which episodes, on which
hikes - and this module is the gate between it and the bucket. Its README
says what a row holds; this says what a row must be before a phone sees it.

JUNK COSTS THE ROW, NEVER THE LIST, the posture client/src/lib/
suggestedHikesData.ts takes toward a document somebody else wrote. But the
somebody here is the maintainer, editing by hand, so a dropped row is never
quiet: `validate` returns every drop with its reason, export_podcasts.py
refuses to upload a list that dropped anything, and
tests/test_export_podcasts.py fails on the committed file for the same
reason. A typo becomes a red pull request, not an episode that never shows.

WHAT IS PUBLISHED, AND WHAT IS NOT. The id, title, show, length and the two
anchors. `note` and `reviewed` stay in the reference file: they are for the
person reviewing the diff, and a phone has no use for either.

NOTHING HERE CHECKS THAT A HIKE ID EXISTS. The suggested hikes are exported
by the vector publish into a release folder this script never reads, so an id
that matches no hike is published and matches nothing on the phone - a card
that does not appear, never a wrong one.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

#: Spotify's base-62 ids are 22 characters. Reasoned from every episode link
#: Spotify prints (`open.spotify.com/episode/<22 chars>`), not from a spec
#: Spotify publishes - its Web API reference calls the id a "base-62
#: identifier" without stating the length. Checked because the id is spliced
#: into a URL the phone opens and a URI the phone sends to Spotify, and a
#: string that is not an id has no business in either.
SPOTIFY_ID_PATTERN = re.compile(r"^[0-9A-Za-z]{22}$")

#: The A.T. is about 2,200 miles from Springer. A range past this is a typo,
#: not a trail the app does not know about yet - the only mile axis the phone
#: holds is the A.T.'s (client/src/lib/hikes.ts, trailHasMileAxis).
MAX_AT_MILE = 2300.0

#: Every field a row may carry. Anything else is a misspelling of one of
#: these, and a misspelt `at_miles` would silently anchor nothing.
ROW_FIELDS = frozenset({"spotify_id", "title", "show", "minutes", "hikes", "at_miles", "reviewed", "note"})


@dataclass(frozen=True)
class Episode:
    spotify_id: str
    title: str
    show: str
    minutes: int | None
    hikes: tuple[str, ...]
    at_miles: tuple[tuple[float, float], ...]


@dataclass
class Validation:
    episodes: list[Episode] = field(default_factory=list)
    #: (row label, reason) for every row that did not make it.
    dropped: list[tuple[str, str]] = field(default_factory=list)


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _minutes(value: object) -> tuple[int | None, str | None]:
    if value is None:
        return None, None
    # bool is an int in Python, and `true` is not a length.
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None, f"minutes must be a positive whole number or absent, not {value!r}"
    return value, None


def _hikes(value: object) -> tuple[tuple[str, ...], str | None]:
    if value is None:
        return (), None
    if not isinstance(value, list) or not all(_text(item) for item in value):
        return (), f"hikes must be a list of hike ids, not {value!r}"
    return tuple(item.strip() for item in value), None


def _ranges(value: object) -> tuple[tuple[tuple[float, float], ...], str | None]:
    if value is None:
        return (), None
    if not isinstance(value, list):
        return (), f"at_miles must be a list of [start, end] pairs, not {value!r}"
    ranges = []
    for pair in value:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(end, int | float) and not isinstance(end, bool) for end in pair)
        ):
            return (), f"each at_miles entry must be [start, end], not {pair!r}"
        start, end = float(pair[0]), float(pair[1])
        if not 0 <= start < end <= MAX_AT_MILE:
            return (), f"at_miles {pair!r} must run forward, inside 0 to {MAX_AT_MILE:g}"
        ranges.append((start, end))
    return tuple(ranges), None


def _reviewed(value: object) -> str | None:
    if not isinstance(value, str):
        return "reviewed must be a date, YYYY-MM-DD"
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return f"reviewed {value!r} is not a YYYY-MM-DD date"
    return None


def validate(rows: list[object]) -> Validation:
    """Every row that can be published, and why each other one cannot."""
    result = Validation()
    seen: set[str] = set()
    for at, row in enumerate(rows):
        label = f"row {at}"
        if not isinstance(row, dict):
            result.dropped.append((label, "not an object"))
            continue
        spotify_id = row.get("spotify_id")
        if isinstance(spotify_id, str):
            label = f"row {at} ({spotify_id})"

        unknown = sorted(set(row) - ROW_FIELDS)
        if unknown:
            result.dropped.append((label, f"unknown field(s) {', '.join(unknown)}"))
            continue
        if not isinstance(spotify_id, str) or not SPOTIFY_ID_PATTERN.match(spotify_id):
            result.dropped.append((label, "spotify_id must be the 22 characters after /episode/ in its link"))
            continue
        if spotify_id in seen:
            result.dropped.append((label, "the same episode is listed twice; merge the two rows"))
            continue
        title, show = _text(row.get("title")), _text(row.get("show"))
        if title is None or show is None:
            result.dropped.append((label, "title and show are both required"))
            continue
        hikes: tuple[str, ...] = ()
        at_miles: tuple[tuple[float, float], ...] = ()
        minutes, why = _minutes(row.get("minutes"))
        if why is None:
            hikes, why = _hikes(row.get("hikes"))
        if why is None:
            at_miles, why = _ranges(row.get("at_miles"))
        if why is None:
            why = _reviewed(row.get("reviewed"))
        if why is None and not hikes and not at_miles:
            why = "needs at least one of hikes or at_miles, or it shows nowhere"
        if why is not None:
            result.dropped.append((label, why))
            continue

        seen.add(spotify_id)
        result.episodes.append(Episode(spotify_id, title, show, minutes, hikes, at_miles))
    return result


def as_published(episode: Episode) -> dict:
    """The phone's copy of a row. `minutes` is left out rather than nulled
    when nobody gave one, the same absent-means-unknown rule the rest of the
    published data keeps."""
    record: dict = {
        "spotify_id": episode.spotify_id,
        "title": episode.title,
        "show": episode.show,
        "hikes": list(episode.hikes),
        "at_miles": [list(pair) for pair in episode.at_miles],
    }
    if episode.minutes is not None:
        record["minutes"] = episode.minutes
    return record
