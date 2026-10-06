"""Appalachian Mountain Club: suggested hikes, its itineraries page read here (decision 54 wave 5, section K,
2026-10-04).

- `amc_itineraries`: outdoors.org/resources/itineraries/, ten trips with an itinerary page in three regions, each
  its name, difficulty, duration and link. Ski, gravel-bike and paddling trips are among them as the page lists
  them; dbt tells a hike from the rest. The itinerary pages themselves are not read, and the New England Trail's
  find-a-hike page renders by script (no hike server-side, the coverage audit).

The reader is extract/_pages_content.py's ContentPages with the `amc_itineraries` site parser: the rows hashed for
the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row
in sources.json holds the terms as found, the live read and the measured key, `link`. not_available.toml [amc_at.suggested_hikes]
draws on this resource: the same page, extracted once here (decision 34).
"""

from extract._pages_content import content_pages

CLAIMS = ("amc_itineraries",)
RESOURCES = [content_pages("amc_itineraries")]
