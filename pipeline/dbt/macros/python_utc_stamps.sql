{#-
    The two ways today's conditions exporters write a UTC timestamp as text,
    so a pub_ writer prints the same characters (#1793, stage 3). Both read a
    TIMESTAMPTZ in UTC whatever the session's time zone, through
    timezone('UTC', ...), and both are null for a null.
-#}

{#- export_conditions.py's _stamp_utc(), which is backend/app/core/time.py's:
    isoformat() of the UTC time with "+00:00" written "Z". isoformat() prints
    the microseconds only when there are any, so 15:00:00.250000 keeps them
    and 15:00:00 does not. -#}
{% macro python_utc_isoformat(ts) -%}
    case
        when {{ ts }} is not null
            then
                strftime(timezone('UTC', {{ ts }}), '%Y-%m-%dT%H:%M:%S')
                || case
                    when strftime(timezone('UTC', {{ ts }}), '%f') != '000000'
                        then '.' || strftime(timezone('UTC', {{ ts }}), '%f')
                    else ''
                end
                || 'Z'
    end
{%- endmacro %}

{#- lib/nynjtc_alerts.py's and lib/atc_updates.py's _as_utc_stamp():
    strftime("%Y-%m-%dT%H:%M:%SZ") of the UTC time, to the second. -#}
{% macro python_utc_seconds(ts) -%}
    strftime(timezone('UTC', {{ ts }}), '%Y-%m-%dT%H:%M:%SZ')
{%- endmacro %}
