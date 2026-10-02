{{ config(format='json', location='highlights.json') }}
-- highlights.json, the stretches of the A.T. somebody says are worth going
-- to (features/CORRIDOR_VIEW.md; #595 — The corridor view has nothing to
-- explore, because "popular" has no source behind it yet), in the shape
-- export_highlights.py writes: the reviewed file the judgement lives in, and
-- every curated row that resolved, in the file's order, each as
-- lib/highlights.py's as_published() writes one.
--
-- A RECORD NAMES ITS BASIS AND NEVER SAYS "POPULAR": `bases` is `named`,
-- the editorial basis and the weakest of the three, cited to OurHike with
-- the reviewer's note and date. The other two are not produced here and not
-- faked. Nothing derived is stored (SH14): no length, no ascent, no Naismith
-- time, which the phone derives from the profile it already holds.
--
-- ALWAYS ONE DOCUMENT, `"highlights": []` when nothing resolved, because
-- export_highlights.py writes the file whatever resolves: a row that cannot
-- be placed is dropped and named (int_suggested_hikes__highlights' warn
-- test), never published with an end guessed.
with highlights as (
    select * from {{ ref('suggested_hikes') }}
    where phone_file = 'highlights'
)

select
    '{{ var("highlights_source") }}' as source,
    coalesce(
        list(
            json_object(
                'id', hike_id,
                'name', name,
                'bases', ['{{ var("highlights_basis") }}'],
                'citations',
                json_object(
                    '{{ var("highlights_basis") }}',
                    json_object(
                        'by', '{{ var("highlights_cited_by") }}',
                        'note', highlight_note,
                        'reviewed', highlight_reviewed
                    )
                ),
                'legs', highlight_legs,
                'club', section_club
            )
            order by list_position
        ),
        []
    ) as highlights
from highlights
