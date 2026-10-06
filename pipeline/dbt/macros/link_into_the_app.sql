{#-
    Why a link a hiker will tap leads back into the app, or null when it does
    not: decision 94 in pipeline/ELT.md, from SEC-3 of PR #1805's second
    review. For a link that has already passed its model's scheme check
    (int_closures__atc_checked's http(s) regex, int_closures__nynjtc_checked's
    starts_with(link, 'http')), both of which pass `https:#access_token=…`.

    The app opens every such link in a new tab, and a new tab of the app signs
    itself in from an `access_token` and `refresh_token` in the URL
    (client/src/lib/safeLink.ts has the trace). So, as a browser would read
    the link - tabs and newlines removed, the spaces and control characters
    at either end dropped, a backslash (chr(92), which `dbt lint` cannot
    parse as a quoted string) read as a slash - three reasons:

    - no host of its own: not `http(s)://` and a host. `https:#…`,
      `https:x` and `https:/x` are all read against the page by an anchor on
      the https app, so they open the app itself;
    - the app's own site: a host that is var('app_host') or under it, after
      the user name and port are dropped, percent escapes decoded, case
      folded and trailing dots removed. dbt_project.yml says where the var
      comes from;
    - a sign-in token anywhere in it: `access_token`, `refresh_token` or
      `code` (a PKCE callback's) with a value, after a `?`, `#` or `&`, in any
      case, percent escapes decoded. On another site too, because a redirect
      keeps the fragment it was reached with (Reasoned; safeLink.ts).

    Each reason reads after "the link", as int_closures__atc_checked and
    int_closures__nynjtc_checked print it. The client refuses the same links at
    every sink (isSafeLink), which is the defence that holds for every source;
    this one keeps them out of what the two checks publish.
-#}
{% macro link_into_the_app(link) -%}
    {%- set app_host = var('app_host') -%}
    {%- set as_read -%}
        replace(
            regexp_replace(
                regexp_replace({{ link }}, '[\t\n\r]', '', 'g'),
                '^[\x{00}-\x{20}]+|[\x{00}-\x{20}]+$',
                '',
                'g'
            ),
            chr(92),
            '/'
        )
    {%- endset -%}
    {%- set host -%}
        rtrim(lower(url_decode(regexp_replace(
            regexp_replace(
                regexp_extract({{ as_read }}, '^https?://([^/?#]*)', 1, 'i'),
                '^.*@',
                ''
            ),
            ':[0-9]*$',
            ''
        ))), '.')
    {%- endset -%}
    case
        when
            not regexp_matches({{ as_read }}, '^https?://[^/?#]', 'i')
            or {{ host }} = ''
            then 'has no host of its own, so the app would open it as one of its own pages'
        when
            {{ host }} = '{{ app_host }}'
            or ends_with({{ host }}, '.{{ app_host }}')
            then 'is on the app''s own site, {{ app_host }}'
        when
            regexp_matches(
                url_decode({{ as_read }}),
                '[?#&](access_token|refresh_token|code)=[^&#]',
                'i'
            )
            then 'carries a sign-in token (access_token, refresh_token or code)'
    end
{%- endmacro %}
