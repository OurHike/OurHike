{{ config(format='json', location='challenges.json') }}
-- challenges.json, the list client/src's challenge screens read, in the
-- shape export_challenges.build_output() writes (decision 44 makes it v1):
-- `source`, the literal naming where the judgement lives, and `challenges`,
-- in the files' path order. No `generated_at`, for export_challenges.py's
-- reason: a stamp moves the sha256 every run, and a run that changed no
-- challenge would still upload one. The date that matters is each record's
-- `reviewed`.
--
-- A record's fields are the mart's, each where build_output() puts it:
-- `window` always an object of two ends that may be null, `finish` and
-- `reward` an object or null, and every item exactly as
-- int_challenges__items published it, `mystery` and `sealed_title` present
-- only where the item has them. An empty mart writes `challenges: []`, which
-- is the exporter's own file when nothing publishes.
with challenges as (
    select * from {{ ref('challenges', v=1) }}
),

records as (
    select
        list_position,
        json_object(
            'id', challenge_id,
            'org', org,
            'trail', trail,
            'name', name,
            'status', status,
            'summary', challenge_summary,
            'window', json_object(
                'opens', window_opens, 'closes', window_closes
            ),
            'finish', case
                when finish_count is not null
                    then json_object(
                        'count', finish_count, 'label', finish_label
                    )
            end,
            'reward', case
                when reward_kind is not null
                    then json_object(
                        'kind', reward_kind,
                        'rules_url', reward_rules_url,
                        'art', reward_art
                    )
            end,
            'takes_entries', takes_entries,
            'photo', photo,
            'sections', sections,
            'items', items,
            'reviewed', reviewed,
            'org_name', org_name,
            'org_short', org_short,
            'org_domain', org_domain
        ) as record
    from challenges
)

select
    -- export_challenges.py's own literal.
    'reference/challenges' as source,
    -- An empty list is [], never null (pipeline/ELT.md's pitfall 2).
    coalesce(
        list(record order by list_position), cast([] as json[])
    ) as challenges
from records
