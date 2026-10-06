"""National Park Service: podcasts, NPS's audio list and one show's feed read here (decision 54 wave 3,
section C, 2026-10-04).

- `nps_multimedia_audio`: NPS's audio list (`/multimedia/audio`), read whole, nationally: 5,173
  items on 2026-10-04, each with its parks, duration, coordinates where it has them, and the audio
  file's URL (never fetched). Oral-history clips and wayside audio descriptions as well as tour
  stops. `transcript` never loads: the oral histories are named private individuals' own accounts of
  their lives (decision 59, Reasoned); the title and description say what a clip is.
- `nps_park_postcards_goga_podcast`: the Park Postcards Podcast for Golden Gate National Recreation
  Area, the one NPS show feed the coverage audit read
  (www.nps.gov/rss/podcasts/podcast_xml.cfm?id=6686775): 9 episodes, 2020-07-20 to 2021-09-22,
  through extract/_content.py's PodcastEpisodes at www.nps.gov's Crawl-delay of 5 s. Its <copyright>
  reads 'Copyright 2026 NPS - For Personal Use Only'. NPS's other show feeds under nps.gov/podcasts/
  are not enumerated.

Each list is read by extract/_content.py's NpsContent, NpsAlerts' reader for another endpoint:
NPS_API_KEY from the environment as the gateway's `X-Api-Key` header, never in a URL, and without it
the change check raises Unavailable, so the table is withdrawn and never read as empty
(extract/_json_apis.py, 'THE KEY'). Every run reads the list (the API sends no validators), 500 a
page, stepping by the rows each page returns; the answer's own `total` is the count and the proof,
and a total that moves within one read or a repeated id raises. Rows land as NPS serves them, nested
lists as JSON, except the row's `person_fields`. dbt assigns each club folder its portion by each
row's own park list matched to nps_alerts' `park_codes` map (decision 34); the folders that draw on
these lists hold via notes naming them. The lane is the type's, monthly.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

National Park Service: podcasts, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Place-tagged audio is the hiker-relevant part. The RSS shows are programming.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): API `/multimedia/audio`: 5,173 items with `durationMs`,
`transcript`, `latitude`/`longitude`, `geometryPoiId`. The sample is oral-history clips (Ellis
Island). Podcast RSS per show: `https://www.nps.gov/rss/podcasts/podcast_xml.cfm?id=6686775` (Park
Postcards, GOGA: 9 items with enclosures, newest 2021-09-22). Listing pages are under
`nps.gov/podcasts/` (search).

Its `where`: https://www.nps.gov/rss/podcasts/podcast_xml.cfm?id=6686775 https://nps.gov/podcasts/
https://nps.gov/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import nps_content, podcast_episodes

CLAIMS = ("nps_multimedia_audio", "nps_park_postcards_goga_podcast")
RESOURCES = [nps_content("nps_multimedia_audio"), podcast_episodes("nps_park_postcards_goga_podcast", crawl_delay=5.0)]
