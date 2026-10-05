{% snapshot int_warnings__history %}
-- The warnings mart's row history (macros/row_history.sql).
--
-- Its key is int_closures__unioned's notice_id, as the closures mart's is,
-- with the same two kinds that are not an id
-- (snapshots/closures/int_closures__history.sql says which).
--
-- `collection_updated` is left out of the hash. It is one value per NWS
-- answer, the `updated` of the whole collection, so it moves whenever NWS's
-- feed does. Hashed, it opened a new version of every active alert whether
-- or not the alert changed: on the fixtures, changing only it re-versioned
-- 5 of 5 NWS alerts (measured 2026-10-05), and the UA soak's saved history
-- grew by 322 to 439 rows between its logged saves over runs 532-538,
-- about one per active alert (read from those runs' logs, 2026-10-05). An
-- alert's own `sent`, `expires` and text are still hashed, so an alert NWS
-- reissues still opens a version. pub_conditions_weather_alerts reads the
-- value it publishes as `nws_updated` from base_nws__alerts, not from the
-- mart.
{{ config(unique_key='warning_id') }}
{{ row_history_snapshot('int_warnings__final', skip=['collection_updated']) }}
{% endsnapshot %}
