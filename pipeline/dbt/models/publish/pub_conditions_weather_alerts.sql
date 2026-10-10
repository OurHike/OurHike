{{ config(
    format='json_document',
    location='conditions_weather_alerts.json',
    meta={'when_empty': 'keep_last_file', 'gate': 'nws_alerts'},
) }}
-- conditions/weather_alerts.json, every relayed NWS alert that reaches a
-- trail square (#1056), in the shape export_weather_alerts.py's bake()
-- writes: its four constants, `fetched_at`, NWS's own `updated`,
-- `generated_at`, the weather squares' `release` and `zone_files`, the
-- alerts in id order, each with NWS's words under bake()'s names, how it was
-- placed and the squares it reaches, and `unknown_zones`.
--
-- WHICH ALERTS: the warnings mart's NWS rows (WN01, WN02: Actual, not a
-- cancellation, NWS's words as written, and only while
-- int_sources__publication lets NWS publish), placed by
-- int_warnings__nws_placed (WN03), and only those that reach a trail square.
-- The mart itself holds every relayed alert and none of the placement, so the
-- hourly lane's other files never wait on the weather squares.
--
-- NO ROW, SO NO FILE, while int_closures__gate holds NWS back (`meta.gate`):
-- when NWS may not publish, the mart holds no NWS row, and `alerts: []` would
-- read as "no warnings", the one thing the warnings line must never say by
-- mistake (WEATHER.md §5); and when no alert landed (below). The phone keeps
-- its last file, and publish.py fails the run after publishing the rest. A
-- missing or doubled weather squares document is a fault in
-- step_weather_squares, not a held source, so it fails the writer.
--
-- `fetched_at` is the alerts' `_loaded_at`: the moment the extract run that
-- asked NWS began, which extract/_run.py stamps on every row it lands. bake()
-- stamps the moment just before its request. The run reads its lane's other
-- resources too, so this can be earlier than the request by as long as
-- they take, and never later: the phone then calls the copy older than it
-- is, the cautious side (Reasoned, from _run.py's checked_at). When NWS
-- answers with no alert at all, nothing landed holds that moment, so the gate
-- holds NWS and the last file stays, as bake() would not (Reasoned: 344 to
-- 486 alerts were active at every read measured, ELT.md; 389 at 2026-10-02
-- 11:23 UTC).
-- A failed NWS request never reaches here: the extract refuses it and the
-- last good table stands, so this rewrites the last answer with its own
-- `fetched_at`, the age the phone shows (export_weather_alerts.py, "IF NWS
-- DOES NOT ANSWER").
--
-- Written verbatim by phone_file's json_document format, because the keys
-- are bake()'s and two of them, `schema` and `source`, would be columns named
-- for keywords.
with alerts as (
    select * from {{ ref('warnings', v=1) }}
    where warning_kind = 'nws_alert'
),

placed as (
    select * from {{ ref('int_warnings__nws_placed') }}
),

-- One row however many documents there are, so a missing or doubled one
-- fails with its reason rather than writing no document at all.
squares_document as (
    select
        count(*) as documents,
        any_value(release) as squares_release,
        any_value(json_extract(squares_document, '$.zone_files')) as zone_files
    from {{ ref('stg_derived__weather_squares') }}
),

gate as (
    select * from {{ ref('int_closures__gate') }}
    where source_key = 'nws_alerts'
),

landed as (
    select
        max(_loaded_at) as fetched_at,
        max(collection_updated) as nws_updated
    from {{ ref('base_nws__alerts') }}
),

published as (
    select
        coalesce(
            list(
                json_object(
                    'id', alerts.alert_id,
                    'event', alerts.alert_event,
                    'headline', alerts.headline,
                    'description', alerts.alert_description,
                    'instruction', alerts.instruction,
                    'severity', alerts.alert_severity,
                    'urgency', alerts.urgency,
                    'certainty', alerts.certainty,
                    'response', alerts.alert_response,
                    'message_type', alerts.message_type,
                    'sent', alerts.sent_at,
                    'effective', alerts.effective_at,
                    'onset', alerts.onset_at,
                    'expires', alerts.expires_at,
                    'ends', alerts.ends_at,
                    'sender_name', alerts.sender_name,
                    'area_desc', alerts.area_desc,
                    'placed_by', placed.placed_by,
                    'squares', cast(placed.squares as json)
                )
                order by alerts.alert_id
            ),
            []
        ) as alert_rows
    from alerts
    inner join placed on alerts.warning_id = placed.notice_id
    where placed.reaches_trail
),

-- Every zone a relayed alert names that the pinned files do not know,
-- whether or not the alert reaches a trail square, as bake() collects them.
unknown_listed as (
    select unnest(cast(cast(unknown_zones as json) as varchar[])) as zone_key
    from placed
),

unknown as (
    select coalesce(list(distinct zone_key order by zone_key), []) as zone_keys
    from unknown_listed
),

judged as (
    select
        landed.fetched_at,
        landed.nws_updated,
        squares_document.documents,
        squares_document.squares_release,
        squares_document.zone_files,
        published.alert_rows,
        unknown.zone_keys,
        gate.passed
    from landed
    cross join squares_document
    cross join published
    cross join unknown
    inner join gate on gate.source_key = 'nws_alerts'
)

select
    case
        when documents != 1
            then error(
                'conditions/weather_alerts.json is not written: '
                || documents
                || ' weather squares documents, where one places every alert'
            )
        else json_object(
            'payload', 'weather_alerts',
            'schema', 1,
            'source', 'National Weather Service, api.weather.gov/alerts/active',
            'credit', 'National Weather Service',
            'fetched_at', {{ python_utc_seconds('fetched_at') }},
            'nws_updated', nws_updated,
            'generated_at', {{ python_utc_seconds(
                'cast(' ~ python_run_stamp() ~ ' as timestamptz)'
            ) }},
            'release', squares_release,
            'zone_files', zone_files,
            'alerts', alert_rows,
            'unknown_zones', zone_keys
        )
    end as document  -- noqa: RF04
from judged
where passed
