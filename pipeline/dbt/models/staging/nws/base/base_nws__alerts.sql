-- Every active NWS alert (extract/_shared/nws/alerts.py), keyed (decision
-- 40), with nothing filtered: Test messages and cancellations are still
-- here, and int_warnings__nws_relayed leaves them out (WN01).
--
-- NWS's words stay as NWS wrote them (WN02): the text fields are renamed and
-- never trimmed or re-cased, and the times stay text, offsets and all,
-- because export_weather_alerts.py relays them exactly and a parse to a
-- timestamp would turn "15:22:00-04:00" into "19:22:00+00". The JSON
-- properties are cast to JSON, and the alert's own polygon, null for an
-- alert NWS places by zone, to a geometry in lon/lat.
--
-- Key: NWS's message id, one per message; an update is a new message.
with source as (
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('nws', 'raw_nws__alerts') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nws_alerts'",
            'id',
        ]) }} as nws_alert_key,
        id as alert_id,
        feature_id,
        status as alert_status,
        messagetype as message_type,
        event as alert_event,
        headline,
        description as alert_description,
        instruction,
        severity as alert_severity,
        urgency,
        certainty,
        response as alert_response,
        sent as sent_at,
        effective as effective_at,
        onset as onset_at,
        expires as expires_at,
        ends as ends_at,
        sendername as sender_name,
        areadesc as area_desc,
        cast(affectedzones as json) as affected_zones,
        cast(geocode as json) as geocode,
        collection_updated,
        st_setcrs(geom, 'OGC:CRS84') as geom,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='nws_alert_key', order_by='_dlt_id'
) }}
