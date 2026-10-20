{#-
    A link carrying an organization's referral query, so its own reports can
    count what came from this app: export_sources.py's `_with_referral`. No
    referral, or an empty one, leaves the link as it is.
-#}
{% macro with_referral(url, referral) -%}
    case
        when coalesce({{ referral }}, '') = '' then {{ url }}
        else {{ url }}
        || case when contains({{ url }}, '?') then '&' else '?' end
        || {{ referral }}
    end
{%- endmacro %}
