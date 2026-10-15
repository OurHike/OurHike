{{ config(materialized='table') }}
-- Every generated club notice source's rows
-- (int_closures__club_notices_unioned, pipeline/generate_notice_models.py),
-- read by decision 53's phase C rules
-- (pipeline/ELT.md, "Every club's closures and alerts", phase C): one row per
-- notice, in the closures family's columns, with whether it blocks the trail
-- and, where it may not publish as current, why. Nothing is dropped here; the
-- finals leave out a row whose `held_because` is set, so the reason stays
-- readable in the warehouse.
--
-- THE RULES, each held by a unit test in _closures__intermediate.yml:
--
-- 1. A NOTICE IS KEPT WHATEVER ITS OWN DATES SAY.
--    ONE WHOSE STATED END HAS PASSED is never read as current. The
--    maintainer's frame A (poll of 2026-10-10): a notice past its own end
--    date stays in the list, greyed, rather than leaving it. Until then this
--    rule held such a notice back, so UA's notices.json of 2026-10-10 17:24
--    UTC carried none of them: 0 of its 1,464 rows with an end date had one
--    already past. Standing Stone's closure pages, which still serve
--    closures that ended in 2022 and 2023 (phase A), now reach a phone that
--    way. conditions/notices.json's `current_until` is that end day
--    (macros/notice_current_until.sql), and the phone greys the notice after
--    it on its own clock, so a phone offline for days greys it on the day,
--    which a build-time hold could not. Rule 3 below still reads it. Its end
--    is the day of `ends_at` in UTC.
--    ONE WHOSE OWN START IS STILL AHEAD PUBLISHES NOW, AS UPCOMING: the
--    maintainer's frame B for wave 6's page 01, P3 (poll of 2026-10-11, "show
--    it now, as upcoming"). Until then this rule held it while its UTC start
--    day was more than one day ahead (Yellowstone's bear management areas,
--    New Jersey's WMA restrictions, King County's alerts and IDPR's emergency
--    closures state one), so a phone that last connected before that day
--    never showed it. It now carries its own `starts_on`, and
--    `obstructs_trail` is rule 3's, read without regard to the start: a
--    closure that starts next month publishes `obstructs_trail` true today.
--    THE PHONE DECIDES THE DAY IT CLOSES, the other half of the same answer:
--    it draws the trail closed only from the day before `starts_on` on its
--    own calendar, and tags the notice "Starts <date>" until then. The day
--    before, because `starts_on` is the UTC day of the source's start
--    instant: in a United States zone behind UTC (UTC-4 to UTC-11) that
--    instant falls on that UTC day or the day before it, and in Guam and
--    the Northern Marianas (UTC+10) on that day or the day after. So a
--    phone in the trail's zone closes the trail up to a day early, or two
--    in Guam and the Northern Marianas, never a day late (Reasoned from the
--    zones' offsets, as client/src/lib/noticeCurrency.ts's obstructsOn()
--    says, not measured on any source). A start the source states as a day
--    alone (an ArcGIS DateOnly field, or epoch milliseconds at UTC midnight)
--    is that day, and the phone closes the trail the whole day before it.
--    `current_until` is not moved by the start
--    (macros/notice_current_until.sql: its own end first), so an upcoming
--    notice with no end and no edit date carries a null one; until its
--    start the phone's tag says what it is.
--    ONE DATE STILL HOLDS A NOTICE BACK (macros/notice_date_holds.sql): an
--    order the source says was rescinded is held, once the build's UTC date
--    is past the UTC day of its rescission. That is the source's own word
--    that the order was lifted, as a status is, not a date OurHike reads an
--    expiry from. An order is lifted at that instant, not at the end of a
--    stated day, and the first build to hold it starts at 00:00 UTC the next
--    day, after the instant whatever the zone it was stated in. So it rounds
--    toward showing an order up to a day after it was lifted, never hiding
--    one still in force (Reasoned, not measured on any source; with no
--    margin, before 2026-10-05, a Denver order rescinded at local midnight
--    was held from 18:00 local the evening before).
-- 2. A NOTICE IS READ BY ITS OWN WORDS, AGAINST ONE VOCABULARY FOR EVERY
--    SOURCE (decision 190; the maintainer, poll of 2026-10-14: "Do by their
--    own words. But make this logic that applies everywhere. we need to stop
--    doing org by org customization."). seeds/notice_words.csv holds each
--    word, the row's own fields it is read in (status, category, title,
--    narrative, site_type: the columns seeds/notice_source_fields.csv maps
--    per source, which is a source's schema, never a meaning; and layer, the
--    layer's own name as its service publishes it, recorded there as
--    layer_title), how it matches and what it reads as. No rule here names a
--    source, and the fact that OurHike files a source under closures is
--    never read as its words (the maintainer's poll of 2026-10-15, "Add the 3
--    fixes"). The one value no shared word
--    can read, a one-letter code, is a row of
--    seeds/notice_word_overrides.csv, which says why; it reads as a word of
--    the vocabulary would, for its own source alone.
--    HOW A WORD MATCHES. `exact`: the field's whole value, case and
--    surrounding space aside. `words`: whole words within the field, every
--    run of characters that are not letters or digits read as one space,
--    and 'non' joined to the word after it, so 'Non-Motorized' and
--    'Nonmotorized' never read as 'motorized'. `code`: exact, on a source
--    whose every stated status is a `code` word, a coded yes/no flag
--    (VTrans's isActive 0 and 1), so a scale that uses 0 (Michigan's burn
--    permits, 0 to 3 with no legend) is never read as a flag.
--    THE READINGS, the first that holds (`reads_as`, with the field and the
--    word that decided it in `read_from`):
--    a. NOT CURRENT: its own status or category is a `not_current` word (an
--       archived, cleared, hidden or open row, a flag's no), whatever the
--       rest says, unless a closing word that `outranks_status` stands
--       unqualified in its status or category: NGPC's Condition 'Not
--       Passable' beside a Road_Status of 'Open' (the Niobrara Bridge
--       section, which its sources.json row says must never show as open)
--       closes, and the Great Allegheny Passage's Hidden still holds its
--       'Fully Obstructed' alert (decision 166). Held, the word in the
--       reason.
--    b. NOTHING FOR A HIKER: a `not_a_hikers_use` word (motorized, OHV,
--       snowmobile) in any of its fields, and no `bars_every_use` word (any
--       use, public entry), no `a_hikers_use` word (foot, stock) and no
--       status that says something else. Decision 165's reading of
--       Michigan's motorized closures, made general: IDPR's five orders that
--       bar motorized use alone leave the phone, its Evans Landing order
--       ("prohibits any use of the trail") does not, and Michigan's 16
--       closures whose own foot-travel status says Temporarily Closed close
--       beside a category of 'Motorized' or 'Multi Use Motorized
--       Nonmotorized' (read live 2026-10-14). Held, the word in the reason.
--    c. CLOSES THE TRAIL, from the first of these that speaks:
--       c1. its status or category holds a `closes_trail` word that no
--           `partly` (Partial, Detour) or `not_a_closure` (Alert, Only)
--           word in the same field qualifies. A word the seed marks
--           `category_needs_title`, 'closure', names in a category the
--           kind of notice the source files the row as, not a state, so
--           there it speaks only where the title holds such a closing
--           word too: USFS's forest orders are typed 'Safety Closure' or
--           'Closure for Resource Protection' whatever they bar ('Forest
--           Wide - Alcohol', 'Reckless Driving'; read live 2026-10-14), so
--           only an order's title says whether it closes an area or a trail.
--           It speaks unless the row is a site (A CLOSED SITE, below);
--       c2. where its status says nothing and its category holds no word of
--           the vocabulary, a placed row's title holds such an unqualified
--           closing word, and the row is no site;
--       c3. where its status says nothing and its category holds no word, A
--           LAYER CLOSES BY ITS OWN NAME ONLY IF THAT NAME SAYS SO (the poll
--           of 2026-10-15): the placed row's layer is named for closures, its
--           own name holding an unqualified closing word, and its title holds
--           no `not_a_closure` word and the row is no site. Named so on
--           2026-10-15: IDPR's 'Emergency Route Closures', Santa Clara's
--           'Areas Closed to the Public', Yosemite's 'Trail Closures
--           (Yosemite)', Superior's 'Closure_Point', Region 6's
--           'Region6FireClosureLine'; Ice Age Trail's 'surveyPoint' and
--           VTrans's 'Notice Line' are not, so their word-silent rows are
--           notices. A `partly` word in a title says which part a line draws
--           (IDPR's Porters Trail Partial Closure) and does not stop it. A
--           page, a feed item or a post is never placed: its title is a
--           headline ('Closures & Notices', 'Now Open: … Bridge Closure',
--           both in the live read of 2026-10-14), read for no closure.
--       A CLOSED SITE IS NOT A CLOSED TRAIL (the poll of 2026-10-15): a
--       closing row is a notice about a site, still listed, where an
--       `a_site_not_the_trail` word (a campground, a yurt, a sno park, a
--       restroom) is the last thing its title names, after any trail word,
--       so 'Horse Camp Trail' is a trail and 'Trail Creek Trailhead' a site;
--       or where its own site type names one (site_type: USFS's recreation
--       sites' 'Campground Camping'); or where it has a site type that names
--       no trail and no hiker's use, and its title and category name none
--       ('Viewing Scenery', where 'Day Hiking' is the trail; a row the source
--       types is a place, @unvalidated for a type no reviewer read: USFS's
--       closed sites state 45 types and 36 state none, read live
--       2026-10-15); or where its category or
--       its layer's own name is a site's ('Trailhead', Florida's 'Campground
--       Status') and neither its title, its category nor its type names a
--       trail. A `bars_every_use` word lifts it, the site's closure then
--       barring entry outright (IDPR's Selway Falls Campground orders).
--       A CLOSURE THAT NAMES ONLY ROADS CLOSES THE ROAD, NOT THE TRAILS
--       AROUND IT (the poll of 2026-10-15): an area (a Polygon or a
--       MultiPolygon) whose title and category name a road and no area, no
--       trail or hiker's use and no entry (`bars_every_use`) reads as a
--       notice ('Seasonal Road Closures on the Evanston/Mt. View Ranger
--       Districts'), where 'Area and Road Closures …' names the area and
--       closes; a line or a point that names a road still closes its own
--       place (IDPR's road orders, as the maintainer chose).
--       A STATUS SAYS NOTHING where it is empty or `unspecified` (-1) on a
--       source that states no status on any row, or is a `stands` word, an
--       on/off flag's yes (Active, Yes, 1). A blank status on a source that
--       states one on other rows says nothing either way, so its row stays
--       a notice: Missouri's blank STATUS, which the maintainer's P1 answer
--       shows as current (decision 164), and 5 of Yellowstone's bear
--       management areas.
--    d. A NOTICE nobody reviewed, otherwise (decision 7: miss rather than
--       cry wolf).
--    A HAZARD AREA (rule 6) is read by its hazard category alone, never by
--    the vocabulary: 'Open' on a shooting range is the hazard, not its
--    absence.
-- 3. A NOTICE CLOSES THE TRAIL ONLY IN A CLOSURES FILE, AND NEVER ONCE ITS
--    OWN END HAS PASSED. `obstructs_trail` is true only where rule 2 reads
--    `closes_trail`, the source files the notice under closures (its club's
--    closures.py), nothing holds it, and its own end day is not more than
--    one day behind the build's UTC date (macros/notice_date_holds.sql's
--    notice_has_ended(): a day stated in a club's own zone has ended
--    everywhere in the United States by 11:00 UTC the day after, American
--    Samoa (UTC-11) being the last zone to finish it and Guam (UTC+10) the
--    first, so the margin reads a closure as closing a day too long, never a
--    day too short; Reasoned, not measured on any source). The USFS R06 fire
--    closures carried 'Active' beside an end date already past on 112 of 938
--    lines, and CDPR 'Full Closure' beside a passed StatusReopenDate is the
--    same shape (pipeline/ELT.md, "Status, water and expiry rules", rule 1):
--    a notice past its end lands in warnings, kept and not current, never in
--    closures. Everything else is null, which decision 7 lands in warnings
--    as not reviewed.
-- 4. PLACE ONLY FROM THE SOURCE'S OWN GEOMETRY, OR ITS STEWARD'S OWN AREA.
--    `geom_geojson` is the staging model's own geometry, never a match of
--    `locality` or a title against a place table: a notice with none is
--    unplaced, and its locality is the source's own words for where
--    (ORG_NOTICES.md section 3). A reviewed term table, the other way phase
--    C allows, does not exist for any of these sources yet.
--    A POINT INSIDE EXACTLY ONE OF ITS STEWARD'S OWN AREAS TAKES THAT AREA,
--    the maintainer's answer to Q3 (poll of 2026-10-11, "Its own boundary",
--    decision 185), chosen as a rule for every steward rather than one for
--    Florida: a notice whose own geometry is a point, of a source
--    seeds/notice_steward_areas.csv links to a layer of its own steward's
--    areas, and inside exactly one area int_closures__steward_areas lets
--    place it (its layer may publish, its key is one raw row's, it is a
--    polygon), has that area's own outline as its place, and `placed_by`
--    names the area. Inside none, or inside two or more, it keeps its point;
--    so does a line, an area, and a point of a source no seed row names.
--    The one source named is Florida's day-use status layer, whose points
--    carry no park id (read live 2026-10-11), placed by FDEP's park
--    boundaries, so a closed park closes the trails inside its boundary
--    (page 01's P5, frame A, decision 168). Measured twice on 2026-10-11, on
--    the live layers' 176 status points and 179 boundaries: for the poll's
--    picture, 169 of the 176 inside exactly one, 33 of the 35 parks closed
--    then; read again at 18:52 UTC for this rule, 173 inside exactly one
--    (each the boundary of the point's own SITE_NAME), none inside two and 3
--    inside none, 11 of the 12 parks closed then. Which way it errs,
--    Reasoned: a closed park placed by its boundary reaches every route
--    through it, and one left at its point reaches only a route within
--    client/src/lib/plannedNotices.ts's NOTICE_REACH_FEET (300) of that
--    point, a miss rather than a wrong place.
--    "Inside" is ST_Within against the outline as drawn: 9 of the 179 are
--    invalid as drawn, ST_Within, ST_Intersects and ST_Covers answered the
--    same 173 with them as drawn and made valid, and making all 179 valid
--    took about 5 s in a loaded sandbox against 0.6 s to parse them
--    (measured 2026-10-11). pub_conditions_notices makes a published shape
--    valid itself.
-- 5. FACTS AND A LINK (decision 55). The columns are the notice's title,
--    category, dates, place and link, and no prose column is carried: the
--    one prose field a source stages, its `narrative`
--    (generate_notice_models.py's PROSE_ROLES), is read by rule 2's words
--    and never selected, and int_warnings__wording_leaks fails the build
--    if one reaches a mart.
-- 6. A HAZARD AREA IS ONLY THE HAZARD ITS OWN CATEGORY SAYS (decision 67).
--    A source seeds/notice_hazard_areas.csv lists with category values
--    publishes only the rows whose own category is one of them: IATA's
--    'No hunting' parcels and NY Parks' safety zones are where hunting is
--    not allowed, and drawing one as a hunting area would tell a hiker the
--    opposite of what the layer says. The rest are held with the category
--    in the reason. A source listed with no category value publishes every
--    row. Its dates are its own (`starts_on`, `ends_on`), and a layer with
--    no season field has none: none of the four hunting layers gives one
--    (seeds/notice_source_fields.csv), so their dates are null, never a
--    season OurHike supplied.
--
-- `key_versions` is how many different raw rows share the notice's key (its
-- base model counts them); int_closures__gate holds a source with any over
-- one.
--
-- `updated_at` is the source's own edit stamp, in ISO 8601 UTC, and null
-- where it gives none: never the load time. `notice_id` is
-- `<source key>:<the source's own id>` (features/ORG_NOTICES.md section 2).
with unioned as (
    select * from {{ ref('int_closures__club_notices_unioned') }}
),

-- Rule 4's areas, each parsed once, its outline as drawn.
steward_areas as (
    select
        source_key,
        areas_source_key || ':' || area_id as area_place,
        geom_geojson,
        st_geomfromgeojson(geom_geojson) as area
    from {{ ref('int_closures__steward_areas') }}
),

-- Each point of a linked source, and how many of its source's areas it lies
-- inside. The type is read from the GeoJSON text, so no other source's
-- geometry is parsed here.
points_in_areas as (
    select
        unioned.notice_key,
        count(steward_areas.area_place) as areas_around,
        any_value(steward_areas.area_place) as area_place,
        any_value(steward_areas.geom_geojson) as area_geojson
    from unioned
    inner join steward_areas
        on
            unioned.source_key = steward_areas.source_key
            and json_extract_string(unioned.geom_geojson, '$.type') = 'Point'
            and st_within(
                st_geomfromgeojson(unioned.geom_geojson), steward_areas.area
            )
    group by unioned.notice_key
),

-- Rule 4: a point inside exactly one of its steward's own areas has that
-- area's outline as its place; every other notice keeps its own geometry.
notices as (
    select
        unioned.* exclude (geom_geojson),
        case
            when points_in_areas.areas_around = 1
                then points_in_areas.area_geojson
            else unioned.geom_geojson
        end as geom_geojson,
        case
            when points_in_areas.areas_around = 1
                then points_in_areas.area_place
        end as placed_by
    from unioned
    left join points_in_areas
        on unioned.notice_key = points_in_areas.notice_key
),

-- Rule 2's vocabulary, one row per word and field it is read in, and each
-- override as a word of its own source alone.
words as (
    select
        lower(trim(word)) as word,
        unnest(string_split(lower(trim(read_in)), ' ')) as field,
        lower(trim(matches)) as matches,
        lower(trim(reads_as)) as reads_as,
        coalesce(outranks_status, false) as outranks_status,
        coalesce(category_needs_title, false) as category_needs_title,
        cast(null as varchar) as only_source
    from {{ ref('notice_words') }}
    union all by name
    select
        lower(trim(value)) as word,
        lower(trim(read_in)) as field,
        'exact' as matches,
        lower(trim(reads_as)) as reads_as,
        false as outranks_status,
        false as category_needs_title,
        source_key as only_source
    from {{ ref('notice_word_overrides') }}
),

-- Each notice's own fields, as rule 2 compares them: the whole value, case
-- and surrounding space aside, and its words padded with a space each side,
-- every run of characters that are not letters or digits one space, 'non'
-- joined to the word after it. The layer's own name is an identifier as often
-- as a phrase ('TemporaryClosure', 'Region6FireClosureLine'), so a capital
-- after a small letter starts a new word there too.
field_values as (
    select
        notice_key,
        source_key,
        'status' as field,
        status as field_value
    from notices
    union all
    select
        notice_key,
        source_key,
        'category' as field,
        category as field_value
    from notices
    union all
    select
        notice_key,
        source_key,
        'title' as field,
        title as field_value
    from notices
    union all
    select
        notice_key,
        source_key,
        'narrative' as field,
        narrative as field_value
    from notices
    union all
    select
        notice_key,
        source_key,
        'site_type' as field,
        site_type as field_value
    from notices
    union all
    select
        notice_key,
        source_key,
        'layer' as field,
        regexp_replace(layer_title, '([a-z])([A-Z])', '\1 \2', 'g')
            as field_value
    from notices
),

field_text as (
    select
        notice_key,
        source_key,
        field,
        lower(trim(field_value)) as whole_value,
        ' ' || trim(
            regexp_replace(
                regexp_replace(
                    lower(field_value), '\bnon[^a-z0-9]+', 'non', 'g'
                ),
                '[^a-z0-9]+',
                ' ',
                'g'
            )
        ) || ' ' as padded_value
    from field_values
    where trim(coalesce(field_value, '')) != ''
),

-- Two facts about each source's own statuses: whether it states one on any
-- row, and whether every one it states is a `code` word (a coded flag).
source_statuses as (
    select
        notices.source_key,
        bool_or(trim(coalesce(notices.status, '')) != '') as states_a_status,
        bool_and(
            trim(coalesce(notices.status, '')) = ''
            or lower(trim(notices.status)) in (
                select codes.word from words as codes
                where codes.matches = 'code'
            )
        ) as states_only_codes
    from notices
    group by notices.source_key
),

-- Every word of the vocabulary each notice's fields hold, and for a `words`
-- match how far from the field's end its last occurrence ends (1 at the end),
-- so a title's last-named thing can be told from the others.
hits as (
    select
        field_text.notice_key,
        field_text.field,
        words.word,
        words.reads_as,
        words.outranks_status,
        words.category_needs_title,
        case
            when words.matches = 'words'
                then
                    strpos(
                        reverse(field_text.padded_value),
                        reverse(' ' || words.word || ' ')
                    )
        end as from_end
    from field_text
    inner join words on field_text.field = words.field
    inner join source_statuses
        on field_text.source_key = source_statuses.source_key
    where
        (
            words.only_source is null
            or words.only_source = field_text.source_key
        )
        and (
            (words.matches = 'exact' and field_text.whole_value = words.word)
            or (
                words.matches = 'code'
                and field_text.whole_value = words.word
                and source_statuses.states_only_codes
            )
            or (
                words.matches = 'words'
                and contains(field_text.padded_value, ' ' || words.word || ' ')
            )
        )
),

-- What each field says, once per notice and field. A `partly` or
-- `not_a_closure` word qualifies a closing word in the same field.
field_readings as (
    select
        notice_key,
        field,
        bool_or(reads_as in ('partly', 'not_a_closure')) as is_qualified,
        bool_or(reads_as = 'not_a_closure') as says_not_a_closure,
        min(word) filter (where reads_as = 'closes_trail') as closing_word,
        min(word) filter (
            where reads_as = 'closes_trail' and not category_needs_title
        ) as closing_state_word,
        coalesce(
            bool_or(outranks_status) filter (where reads_as = 'closes_trail'),
            false
        ) as closing_outranks,
        min(word) filter (where reads_as = 'not_current') as not_current_word,
        min(word) filter (
            where reads_as = 'not_a_hikers_use'
        ) as not_a_hikers_use_word,
        bool_or(reads_as = 'bars_every_use') as bars_every_use,
        bool_or(reads_as = 'a_hikers_use') as names_a_hikers_use,
        min(word) filter (where reads_as = 'a_site_not_the_trail') as site_word,
        min(from_end) filter (
            where reads_as = 'a_site_not_the_trail'
        ) as site_from_end,
        bool_or(reads_as in ('names_a_trail', 'a_hikers_use'))
            as names_a_trail,
        min(from_end) filter (
            where reads_as in ('names_a_trail', 'a_hikers_use')
        ) as trail_from_end,
        min(word) filter (where reads_as = 'names_a_road') as road_word,
        bool_or(reads_as = 'names_an_area') as names_an_area,
        bool_or(reads_as = 'stands') as stands,
        bool_or(reads_as = 'unspecified') as unspecified
    from hits
    group by notice_key, field
),

-- What each notice's words say, its fields side by side; each `..._from`
-- is the field and the word, as `read_from` prints them.
said as (
    select
        notice_key,
        coalesce(
            min('status ''' || not_current_word || '''')
            filter (where field = 'status'),
            min('category ''' || not_current_word || '''')
            filter (where field = 'category')
        ) as not_current_from,
        min(field || ' ''' || not_a_hikers_use_word || '''')
            as not_a_hikers_use_from,
        bool_or(bars_every_use) as bars_every_use,
        bool_or(names_a_hikers_use) as names_a_hikers_use,
        min('title ''' || site_word || '''')
        filter (where field = 'title') as title_site_from,
        coalesce(
            bool_or(site_from_end < coalesce(trail_from_end, 2147483647))
            filter (where field = 'title'),
            false
        ) as title_names_a_site_last,
        min('site_type ''' || site_word || '''')
        filter (where field = 'site_type') as type_site_from,
        coalesce(
            min('category ''' || site_word || '''')
            filter (where field = 'category'),
            min('layer ''' || site_word || '''')
            filter (where field = 'layer')
        ) as kind_site_from,
        coalesce(
            bool_or(names_a_trail)
            filter (where field in ('title', 'category')),
            false
        ) as names_a_trail,
        coalesce(
            bool_or(names_a_trail) filter (where field = 'site_type'), false
        ) as type_names_a_trail,
        min(field || ' ''' || road_word || '''')
        filter (where field in ('title', 'category')) as road_from,
        coalesce(
            bool_or(names_an_area)
            filter (where field in ('title', 'category')),
            false
        ) as names_an_area,
        min('layer ''' || closing_word || '''')
        filter (where field = 'layer' and not is_qualified)
            as layer_closes_from,
        coalesce(
            min('status ''' || closing_word || '''')
            filter (where field = 'status' and not is_qualified),
            min('category ''' || closing_state_word || '''')
            filter (where field = 'category' and not is_qualified)
        ) as closes_from,
        min('category ''' || closing_word || '''')
        filter (where field = 'category' and not is_qualified)
            as category_kind_from,
        coalesce(
            bool_or(closing_outranks) filter (
                where field in ('status', 'category') and not is_qualified
            ),
            false
        ) as closing_outranks,
        min('title ''' || closing_word || '''')
        filter (where field = 'title' and not is_qualified)
            as title_closes_from,
        coalesce(
            bool_or(says_not_a_closure) filter (where field = 'title'), false
        ) as title_says_not_a_closure,
        coalesce(bool_or(stands) filter (where field = 'status'), false)
            as status_stands,
        coalesce(bool_or(unspecified) filter (where field = 'status'), false)
            as status_unspecified,
        coalesce(
            bool_or(not_a_hikers_use_word is not null)
            filter (where field = 'status'),
            false
        ) as status_names_a_use_hikers_are_not,
        coalesce(bool_or(field = 'category'), false) as category_holds_a_word
    from field_readings
    group by notice_key
),

-- Rule 6's seed: each hazard source once, with whether every row is the
-- hazard, and its category values as compared.
hazard_sources as (
    select
        source_key,
        any_value(hazard) as hazard,
        bool_or(coalesce(trim(category_value), '') = '') as every_row
    from {{ ref('notice_hazard_areas') }}
    group by source_key
),

hazard_values as (
    select distinct
        source_key,
        lower(trim(category_value)) as category_value
    from {{ ref('notice_hazard_areas') }}
    where coalesce(trim(category_value), '') != ''
),

-- Each notice with what its words say (rule 2), its hazard (rule 6) and its
-- dates (rule 1).
read_words as (
    select
        notices.*,
        said.not_current_from,
        said.not_a_hikers_use_from,
        coalesce(
            said.closes_from,
            case
                when said.title_closes_from is not null
                    then
                        said.category_kind_from || ' with its '
                        || said.title_closes_from
            end
        ) as closes_from,
        said.title_closes_from,
        said.layer_closes_from,
        coalesce(said.bars_every_use, false) as bars_every_use,
        coalesce(said.names_a_hikers_use, false) as names_a_hikers_use,
        case
            when coalesce(said.bars_every_use, false) then null
            when said.title_names_a_site_last then said.title_site_from
            when said.type_site_from is not null then said.type_site_from
            when
                trim(coalesce(notices.site_type, '')) != ''
                and not coalesce(said.type_names_a_trail, false)
                and not coalesce(said.names_a_trail, false)
                then 'site_type ''' || lower(trim(notices.site_type)) || ''''
            when
                said.kind_site_from is not null
                and not coalesce(said.type_names_a_trail, false)
                and not coalesce(said.names_a_trail, false)
                then said.kind_site_from
        end as site_from,
        coalesce(
            json_extract_string(notices.geom_geojson, '$.type')
            in ('Polygon', 'MultiPolygon')
            and said.road_from is not null
            and not said.names_an_area
            and not said.names_a_trail
            and not said.bars_every_use,
            false
        ) as area_names_only_a_road,
        said.road_from,
        coalesce(said.closing_outranks, false) as closing_outranks,
        coalesce(said.title_says_not_a_closure, false)
            as title_says_not_a_closure,
        coalesce(said.status_stands, false) as status_stands,
        coalesce(said.status_names_a_use_hikers_are_not, false)
            as status_names_a_use_hikers_are_not,
        coalesce(said.category_holds_a_word, false) as category_holds_a_word,
        (
            trim(coalesce(notices.status, '')) = ''
            or coalesce(said.status_unspecified, false)
        ) as status_is_blank,
        source_statuses.states_a_status,
        notices.geom_geojson is not null as is_placed,
        hazard_sources.hazard,
        coalesce(hazard_sources.every_row, false) as hazard_every_row,
        hazard_values.category_value is not null as hazard_category_listed,
        cast(timezone('UTC', notices.starts_at) as date) as starts_on,
        cast(timezone('UTC', notices.ends_at) as date) as ends_on,
        cast(timezone('UTC', notices.rescinded_at) as date) as rescinded_on,
        {{ notice_build_date() }} as build_date
    from notices
    left join said on notices.notice_key = said.notice_key
    inner join source_statuses
        on notices.source_key = source_statuses.source_key
    left join hazard_sources
        on notices.source_key = hazard_sources.source_key
    left join hazard_values
        on
            notices.source_key = hazard_values.source_key
            and lower(trim(notices.category)) = hazard_values.category_value
),

-- Rule 2's readings, the first that holds: which one, as a short name.
-- A status says nothing where it is blank on a source that states none, or
-- an on/off flag's yes; it says something else where it is neither blank,
-- a flag's yes, nor itself a use a hiker is not.
ruled as (
    select
        *,
        case
            when hazard is not null then 'hazard'
            when not_current_from is not null and not closing_outranks
                then 'a'
            when
                not_a_hikers_use_from is not null
                and not bars_every_use
                and not names_a_hikers_use
                and (
                    status_is_blank
                    or status_stands
                    or status_names_a_use_hikers_are_not
                )
                then 'b'
            when
                closes_from is not null
                and site_from is not null
                and not closing_outranks
                then 'site'
            when closes_from is not null then 'c1'
            when
                ((status_is_blank and not states_a_status) or status_stands)
                and not category_holds_a_word
                and is_placed
                and site_from is not null
                then 'site'
            when
                ((status_is_blank and not states_a_status) or status_stands)
                and not category_holds_a_word
                and is_placed
                and title_closes_from is not null
                then 'c2'
            when
                ((status_is_blank and not states_a_status) or status_stands)
                and not category_holds_a_word
                and is_placed
                and layer_closes_from is not null
                and not title_says_not_a_closure
                then 'c3'
            else 'd'
        end as reading_rule
    from read_words
),

-- Rule 1's one date hold comes last, from macros/notice_date_holds.sql;
-- rule 3's end date is `has_ended`, which holds nothing back.
judged as (
    select
        *,
        case
            when reading_rule = 'a' then 'not_current'
            when reading_rule = 'b' then 'nothing_for_a_hiker'
            when
                reading_rule in ('c1', 'c2', 'c3') and area_names_only_a_road
                then 'notice'
            when reading_rule in ('c1', 'c2', 'c3') then 'closes_trail'
            else 'notice'
        end as reads_as,
        case
            when reading_rule = 'a' then not_current_from
            when reading_rule = 'b' then not_a_hikers_use_from
            when
                reading_rule in ('c1', 'c2', 'c3') and area_names_only_a_road
                then road_from || ', an area that names only a road'
            when reading_rule = 'c1' then closes_from
            when reading_rule = 'c2' then title_closes_from
            when reading_rule = 'c3' then layer_closes_from
            when reading_rule = 'site'
                then site_from || ', a site and not the trail'
        end as read_from,
        case
            when reading_rule = 'a'
                then
                    'its own ' || not_current_from
                    || ' says the notice is not current '
                    || '(seeds/notice_words.csv)'
            when reading_rule = 'b'
                then
                    'its own ' || not_a_hikers_use_from
                    || ' limits it to a use a hiker is not, and none of its '
                    || 'words bars every use: nothing for a hiker '
                    || '(seeds/notice_words.csv)'
            when
                hazard is not null
                and not hazard_every_row
                and not hazard_category_listed
                then
                    'its own category, ' || coalesce(category, 'none')
                    || ', is not one notice_hazard_areas reads as '
                    || hazard
            {{ notice_date_holds('build_date', 'rescinded_on') }}
        end as held_because,
        {{ notice_has_ended('ends_on', 'build_date') }} as has_ended
    from ruled
)

select
    source_key || ':' || coalesce(source_id, 'key-' || notice_key) as notice_id,
    notice_key as source_row_key,
    'club_' || reader as notice_kind,
    club,
    source_key,
    notice_type,
    listing,
    case
        when
            notice_type = 'closures'
            and reads_as = 'closes_trail'
            and held_because is null
            and not has_ended
            then true
    end as obstructs_trail,
    case
        when
            notice_type = 'closures'
            and reads_as = 'closes_trail'
            and held_because is null
            and not has_ended
            then 'org_published'
        else 'not_reviewed'
    end as review_state,
    {{ python_html_unescape('title') }} as title,
    category,
    status,
    reads_as,
    read_from,
    locality,
    starts_at,
    starts_on,
    ends_on,
    rescinded_on,
    source_edited_at,
    strftime(timezone('UTC', source_edited_at), '%Y-%m-%dT%H:%M:%SZ')
        as updated_at,
    source_url,
    geom_geojson,
    placed_by,
    held_because,
    key_versions,
    _loaded_at
from judged
