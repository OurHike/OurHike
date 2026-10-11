"""Monadnock-Sunapee Greenway Trail Club: suggested hikes, the two routes its FAQ recommends (decision 54's wave 5,
section K's per-site readers, 2026-10-10).

- `msgtc_best_routes`: msgtc.org/faq/'s two 'Best Route' questions, each the question as written, the route its
  answer names ('We recommend taking the Summit Trail (also the SRK Trail) (2.1 miles).') and the distance where
  the answer states one. The rest of each answer is the club's wording and is not read.

The reader is extract/_pages_content.py's ContentPages with the `msgtc_best_routes` site parser: the rows hashed for
the change check (no page validator decides FRESH), facts and the link only, never the club's own wording.
msgtc.org's robots.txt asks `Crawl-delay: 10` (read 2026-10-10), so the one request waits it. Its row in
sources.json holds the terms as found, the live read and the measured key, the question.
"""

from extract._pages_content import content_pages

CLAIMS = ("msgtc_best_routes",)
RESOURCES = [content_pages("msgtc_best_routes", crawl_delay=10.0)]
