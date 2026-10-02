{{ config(format='json', location='conditions_nynjtc_alerts.json') }}
-- conditions/nynjtc_alerts.json, NYNJTC's Trail Alerts, in the shape
-- export_nynjtc_alerts.py's build_document() writes: `generated_at` and
-- every alert by slug, each as lib/nynjtc_alerts.py's published_rows()
-- writes one. No `reviewed_at`: nobody has reviewed NYNJTC's page, and that
-- exporter's docstring says why inventing one would claim a review that did
-- not happen.
--
-- WHICH ROWS: NYNJTC's notices in both marts. Today every one lands in the
-- warnings mart, because nobody has classified one (decision 7), and the
-- file's own fields stay as they are (decision 44): `place` unplaced,
-- `category` null and `review_state` unreviewed, each lib/nynjtc_alerts.py's
-- constant, "never a placeholder that a later change should quietly relax"
-- (WN06). `obstructs_trail` is false for an unclassified notice, as that
-- file has always written it, and the mart's own value where one is known,
-- so a notice classified as blocking can never go out as passable.
--
-- NOTHING IS WRITTEN for a source int_closures__gate holds back, as
-- pub_conditions_atc_updates says: the model fails before the copy and the
-- phone keeps its last good file.
with nynjtc_rows as (
    select
        closure_id as notice_id,
        obstructs_trail,
        title,
        locality,
        updated_at,
        source_url
    from {{ ref('closures', v=1) }}
    where source_key = 'nynjtc_trail_alerts'
    union all
    select
        warning_id as notice_id,
        obstructs_trail,
        title,
        locality,
        updated_at,
        source_url
    from {{ ref('warnings', v=1) }}
    where source_key = 'nynjtc_trail_alerts' and warning_kind = 'org_notice'
),

gate as (
    select * from {{ ref('int_closures__gate') }}
    where source_key = 'nynjtc_trail_alerts'
),

-- `notice_id` is `nynjtc_trail_alerts:` and the slug, so its order is the
-- slugs' order, which is published_rows()'s `sorted(alerts)`.
published as (
    select
        coalesce(
            list(
                json_object(
                    'notice_id', notice_id,
                    'source_key', 'nynjtc_trail_alerts',
                    'title', title,
                    'category', null,
                    'locality', locality,
                    'place', json_object('kind', 'unplaced'),
                    'obstructs_trail', coalesce(obstructs_trail, false),
                    'updated_at', updated_at,
                    'source_url', source_url,
                    'review_state', 'unreviewed'
                ) order by notice_id
            ),
            []
        ) as nynjtc_alerts
    from nynjtc_rows
),

judged as (
    select
        published.nynjtc_alerts,
        coalesce(gate.passed, false) as passed,
        coalesce(
            gate.held_because,
            'int_closures__gate has no row for nynjtc_trail_alerts'
        ) as held_because
    from published
    left join gate on gate.source_key = 'nynjtc_trail_alerts'
)

select
    case
        when passed
            then {{ python_run_stamp() }}
        else error(
            'conditions/nynjtc_alerts.json is not written: ' || held_because
        )
    end as generated_at,
    nynjtc_alerts
from judged
