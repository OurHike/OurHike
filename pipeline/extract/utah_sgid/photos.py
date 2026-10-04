"""Utah SGID: photos, arriving on the state park points layer, which places.py's
`ugrc_state_park_points` lands (decision 54 wave 3, section C, 2026-10-04).

`thumbnail_url` holds a website image on 54 of 54 rows (the coverage audit's skeptic), so the
manifest rows arrive with that layer and this type shares it. No licence is stated for the images,
and the one sampled sat on a staging host (stateparks.stage.utah.gov), so none publishes on the
layer's word.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Utah UGRC — SGID Trails and Pathways: photos, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

The photos are Utah State Parks' website thumbnails, not UGRC's, and a staging host can vanish
without notice. Owner of the rights: Utah State Parks (Reasoned from the host). `may_publish` false
until settled. Worth little.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `state_park_points_for_website.thumbnail_url` points at
`stateparks.utah.gov/wp-content/uploads/…`, website images with no licence stated. Skeptic re-
checked: 54 of 54 rows carry a URL. The one sampled is a 300×169 `.webp` on
`stateparks.stage.utah.gov`, a staging host. Also present: `Utah_Alluvial_Fans_Field_Photos`, which
are geology field photos, not hiker features.

Its `where`: https://stateparks.utah.gov/wp-content/uploads/ https://stateparks.stage.utah.gov
https://gis.utah.gov/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "places"
