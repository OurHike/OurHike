"""Society for the Protection of New Hampshire Forests: challenges, its Forest Reservation Challenge's 33 reservations
(decision 54's wave 5, section K's per-site readers, 2026-10-10).

- `spnhf_forest_reservation_challenge`: forestsociety.org/challenge states 'Tier 1 (33 Reservations)'; the site's
  sitemap lists one /forest-reservation-challenge-<name> page a reservation, and each lands its reservation's name,
  its Tier 2 region, its own link and its Reservation Guide page. The list is held to the stated count. The selfie
  locations and discovery questions are the Society's wording and are not read; the 5 Hikes Challenge, a dated fall
  event, is not read either.

The reader is extract/_pages_content.py's ContentPages with the `spnhf_forest_reservation_challenge` site parser: the
rows hashed for the change check (no page validator decides FRESH), facts and the links only. www.forestsociety.org's
robots.txt asks no Crawl-delay (read 2026-10-10), so the 35 requests keep DEFAULT_HOST_GAP_SECONDS between them.
Its row in sources.json holds the terms as found, the live read and the measured key, the reservation's name.
"""

from extract._pages_content import content_pages

CLAIMS = ("spnhf_forest_reservation_challenge",)
RESOURCES = [content_pages("spnhf_forest_reservation_challenge")]
