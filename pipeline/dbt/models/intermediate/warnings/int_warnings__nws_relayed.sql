-- The NWS alerts OurHike relays (export_weather_alerts.py's relayed()):
-- every alert NWS marks `Actual` that is not a cancellation (WN01), with
-- NWS's own words and times exactly as it wrote them and null where it
-- sent null (WN02: "an alert with no `ends` has not been given one, which is
-- not the same as ending now"). The maintainer's "relay all" (2026-09-26,
-- HIKER_SAFETY.md §3): none is left out for being the wrong kind.
--
-- WHERE AN ALERT LANDS IS NOT HERE (WN03). int_warnings__nws_placed puts
-- each alert on the NBM weather squares build_weather_squares.py chose, by
-- the alert's polygon when it has one and its zones otherwise, as
-- export_weather_alerts.py does, and pub_conditions_weather_alerts writes
-- the ones that reach a trail square. This relays every alert in the US and
-- keeps each one's polygon and zones for that placement, so the warnings
-- mart holds more alerts than conditions/weather_alerts.json does: every
-- relayed one, and none of the squares, which keeps the hourly lane's
-- other files from waiting on the weather squares.
with alerts as (
    select * from {{ ref('base_nws__alerts') }}
)

select
    'nws_alerts:' || alert_id as notice_id,
    nws_alert_key as source_row_key,
    'nws_alert' as notice_kind,
    'nws' as club,
    'nws_alerts' as source_key,
    false as obstructs_trail,
    'relayed' as review_state,
    alert_id,
    alert_event,
    headline,
    alert_description,
    instruction,
    alert_severity,
    urgency,
    certainty,
    alert_response,
    message_type,
    sent_at,
    effective_at,
    onset_at,
    expires_at,
    ends_at,
    sender_name,
    area_desc,
    affected_zones,
    try_cast(sent_at as timestamptz) as source_edited_at,
    collection_updated,
    cast(st_asgeojson(geom) as varchar) as geom_geojson,
    _loaded_at
from alerts
where
    alert_status = 'Actual'
    and coalesce(message_type, '') != 'Cancel'
