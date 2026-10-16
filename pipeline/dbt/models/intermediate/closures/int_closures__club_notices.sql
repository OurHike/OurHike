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
--    ONE WHOSE OWN WORDS STATE A SEASON IS READ IN THE SEASON THAT HAS NOT
--    ENDED (pipeline/ELT.md, "Status, water and expiry rules", rule 4: an
--    expiry "neither infinite nor last year's date"; the review of
--    2026-10-15, S1-3). A source whose seeds/notice_source_fields.csv row
--    names a `season` field states there, in words, a period that recurs
--    every year ('December 1 - April 30'), beside the dated instance it
--    last set: COTREX's Closure_Period, beside last season's Start_Date and
--    End_Date. Where the row states no end, or its own end has passed by
--    rule 3's margin, its `starts_on` and `ends_on` are that period in the
--    first year whose end has not (macros/notice_season.sql): the season
--    under way, or the next one, which publishes as upcoming like any notice
--    whose start is ahead. A period that wraps the year ('November 1 -
--    March 14') ends in the year after it starts. A season field that
--    states no such range ('Year-round', a year, a list of nights) is no
--    season, and the row keeps its own dates. `starts_at` stays the
--    source's own instant. Read live 2026-10-15: 108 of COTREX's 128 rows
--    state a range, and every one of their own End_Dates had passed.
--    @unvalidated that a range stated with no year means every year: it is
--    the plain reading of COTREX's own words, its layer is the one it
--    overwrote in October 2025 ('SCs_All_COTREX_Oct2025_…'), and nobody has
--    asked COTREX whether each closure is set again this season.
--    ONE WHOSE OWN TITLE STATES ITS END ENDS THEN, or on its own end date
--    where that is later (decision 213, rule 13, the maintainer's poll of
--    2026-10-15): 'Closed Until 2027', '(2026-2027)', 'Sept. 8, 2026 through
--    June 2027' (macros/notice_title_end_day.sql, which says what it reads
--    and what it refuses). A month alone is its last day and a year alone
--    its December 31, toward caution. `ends_on` is that later day, so rule 3
--    and `current_until` read it as they read any end: a title that names a
--    passed end greys its row, one that names a later end keeps it current
--    past its edit date's 90 days. Until then only a duration a title states
--    ('closed for 3 to 6 months', macros/notice_current_until.sql) was read.
--
--    A RECURRING SEASON PUBLISHES ONLY FROM 30 DAYS BEFORE IT STARTS
--    (decision 213, rule 9, the maintainer's poll of 2026-10-15, "Hold until
--    a month before", over the recommended "publish when read"). A row
--    whose own words state a season, as above, and whose `starts_on` is
--    more than `notice_season_lead_days` after the build's UTC date is held,
--    for every source with a season field. From that day it publishes as
--    upcoming like any notice whose start is ahead, and the phone closes the
--    trail from the day before `starts_on`. The rule names recurring
--    seasons and is no wider: a notice whose start is ahead and which states
--    no season (USFS Region 4's forest orders, IDPR's emergency closures)
--    still publishes when read, as the next paragraph has it (decision 167).
--    A phone that does not connect between the 30th day before a season and
--    its start does not learn of that season until it does. Read live
--    2026-10-15: of COTREX's 128 rows, 99 had a `starts_on` after 2026-11-14
--    in UA's conditions/notices.json of 21:26 UTC (88 of them closing a
--    trail: 52 crossed out and 36 shaded in its trail_closures.json). This
--    holds those 99 until their 30th day before: each is a season's start
--    (Reasoned: every one of the 108 rows stating a range had its own end
--    already passed, and a start that far ahead is no row's own).
--    ONE WHOSE OWN DATES CONTRADICT EACH OTHER CLOSES NO TRAIL (status rule
--    1's contradiction test, for the shape the review of 2026-10-15 found,
--    S2-5): an end before its own start, or a start or an end before 1900
--    (Yellowstone's GALLATIN states an end of 0023-11-10). Its
--    `obstructs_trail` is null, so decision 7 lands it in warnings as not
--    reviewed, both dates kept for the phone to show. It is read after a
--    season moves the dates, so a season that wraps the year (COTREX's
--    'Seasonal Waterfowl Closure of Boat Ramps', stated 2025-11-01 to
--    2025-03-14) is read in its season, not as a contradiction. Live,
--    2026-10-15: IDPR's 'White Pine Fire Scar Closure' (start 2027-06-05,
--    end 2027-05-31) was the one such row closing a trail.
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
--    whose every stated status is a `code` word or an `unspecified` one, a
--    coded yes/no flag (VTrans's isActive 0 and 1, and -1 its coded
--    Unknown, which the review of 2026-10-15 found turned the source's one
--    active closure into a notice and published its 19 inactive rows, S2-1),
--    so a scale that uses 0 (Michigan's burn permits, 0 to 3 with no legend)
--    is never read as a flag. A QUALIFYING WORD INSIDE A `not_a_qualifier`
--    PHRASE QUALIFIES NOTHING: 'closed until further notice' is closed, 'no
--    detour available' names no way around, and 'authorized personnel only'
--    bars every hiker (the review of 2026-10-15, S2-3), where 'notice',
--    'detour' and 'only' elsewhere qualify a closing word beside them
--    ('Hiker Notice: … vehicular closure', 'Closure with Detour', 'Foot
--    only').
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
--       Nonmotorized' (read live 2026-10-14). A phrase that names both
--       kinds of use, or closes the trail to everyone, bars every use
--       ('motorized and non-motorized use', 'closed to all users', 'closed to
--       the public'; the review of 2026-10-15, S2-2), where the bare
--       'non-motorized' does not: IDPR's Lightning Creek 419 order says
--       'non-motorized use no longer prohibited'. Held, the word in the
--       reason.
--    c. CLOSES THE TRAIL, from the first of these that speaks:
--       c1. its status or category holds a `closes_trail` word that no
--           `partly` (Partial), `a_way_around` (Detour, Reroute),
--           `not_a_closure` (Alert, Only) or `states_a_start` (Beginning)
--           word in the same field qualifies. A word the seed marks
--           `category_needs_title`, 'closure', names in a category the
--           kind of notice the source files the row as, not a state, so
--           there it speaks only where the title holds such a closing
--           word too: USFS's forest orders are typed 'Safety Closure' or
--           'Closure for Resource Protection' whatever they bar ('Forest
--           Wide - Alcohol', 'Reckless Driving'; read live 2026-10-14), so
--           only an order's title says whether it closes an area or a trail.
--           A CATEGORY THAT IS A CLOSING WORD ALONE ('Closure', 'Closed')
--           is no kind beside others but the row's whole statement, so on a
--           placed row it closes by itself (decision 213, rule 1, the
--           maintainer's poll of 2026-10-15): CDTC's 18 current alerts typed
--           'Closure' and titled by place ('Camp Creek Fire') close, where
--           until then they were notices. Placed, as c2 is, because an
--           unplaced row is a page or a feed item whose category files a
--           headline ('DCR park alerts and advisories', typed 'Closure').
--           It speaks unless the row is a site (A CLOSED SITE, below);
--       c2. where its status says nothing and its category holds no word of
--           the vocabulary, a placed row's title holds such an unqualified
--           closing word, and the row is no site. A CATEGORY'S RESTRICTION
--           WORD KEEPS NO TITLE QUIET (decision 213, rule 2): a category whose
--           words are a kind of order the seed marks `category_needs_title`
--           ('restriction', 'restrictions'), beside nothing but a place
--           ('area', 'trail', 'road'), lets the title speak, so USFS R04's
--           'Roaring River & William Pogue NRT Trail Closure', typed 'Other
--           Restriction', closes. A LAYER NAMED FOR A WAY AROUND, its own
--           name holding an `a_way_around` word and no closing word, draws
--           the way around, so its title's closing word names what the line
--           avoids and closes nothing (decision 213, rule 5's reading of a
--           layer's name as every row's words): CDTC's 'Reroutes' line
--           'Hopewell Lake Construction Closure', which decision 213's rule 8
--           would otherwise cross out. A START STATED IN THE
--           TITLE: a `states_a_start` word there qualifies the closing word
--           only where no day follows it. Where one does ('Hunting Closure
--           beginning 9/1', 'Closed (Beginning Oct. 28, 2026)'), that day is
--           when the closure starts (macros/notice_title_start_day.sql: a
--           year the title leaves out is the first that puts the day on or
--           after the row's own start, else its own edit date), the row
--           closes, and its `starts_on` is the later of its own start and
--           that day, so the phone closes the trail from the day before it
--           as for any start (decision 167); so does a c1 row whose
--           category's 'closure' closes by that title. Until the review of
--           2026-10-15 (S1-4) such a row was a notice for ever, IATA's two
--           hunting closures among them;
--       c3. where its status says nothing and its category holds no word, A
--           LAYER CLOSES BY ITS OWN NAME ONLY IF THAT NAME SAYS SO (the poll
--           of 2026-10-15): the placed row's layer is named for closures, its
--           own name holding an unqualified closing word, and its title holds
--           no `not_a_closure` word, no `a_way_around` word and no start it
--           states no day for, and the row is no site. A title that names a
--           way around is the way around: PCTA's 'Closure Line' layer draws
--           its detours ('Rattlesnake Flats detour'), which its name crossed
--           out until the review of 2026-10-15 (S2-4). Named so on
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
--       closing row is a notice about a site, still listed, where its title
--       names only sites. A title names each thing it lists (the parts
--       between '&', '+', a comma, a slash, a spaced dash, 'and' or 'or'),
--       and each thing is what the last of its site or trail words names:
--       'Horse Camp Trail' is a trail and 'Trail Creek Trailhead' a site,
--       'Luzerne Horse Trail Campground and Trailhead' two sites, and 'Trail
--       & Parking Area Closure' a trail and a site, so the trail is closed
--       (the decision row's "unless its title … names a trail"; until the
--       review of 2026-10-15, S1-2, the title's last-named thing alone
--       decided, and IATA's 'Trail & Parking Area Closure' read as a site).
--       Or where its own site type names one (site_type: USFS's recreation
--       sites' 'Campground Camping'); or where it has a site type that names
--       no trail and no hiker's use, and its title and category name none
--       ('Viewing Scenery', where 'Day Hiking' is the trail): a row the
--       source types is a place. That catch-all reads 234 of USFS's closed
--       or temporarily closed recreation sites (published, read live
--       2026-10-15) as sites: interpretive sites, overlooks and lookouts,
--       lakes and beaches, scenic byways, OHV and snow-play areas, caves,
--       and 55 typed 'Intermediate Parent Group', some of which are areas
--       ('Joyce Kilmer-Slickrock Wilderness Area') and some roads; whether
--       an area so typed should close is the maintainer's (the review of
--       2026-10-15, S1-2), @unvalidated until then. Or where its category
--       or its layer's own name is a site's ('Trailhead', Florida's
--       'Campground Status') and neither its title, its category nor its
--       type names a trail. A `bars_every_use` word lifts it, the site's
--       closure then barring entry outright (IDPR's Selway Falls Campground
--       orders).
--       A CLOSURE THAT NAMES ONLY ROADS CLOSES THE ROAD, NOT THE TRAILS
--       AROUND IT (the poll of 2026-10-15): an area (a Polygon or a
--       MultiPolygon) whose title and category name a road and no area, no
--       trail or hiker's use and no entry (`bars_every_use`) reads as a
--       notice ('Seasonal Road Closures on the Evanston/Mt. View Ranger
--       Districts'), where 'Area and Road Closures …' names the area and
--       closes; a line or a point that names a road still closes its own
--       place (IDPR's road orders, as the maintainer chose). A LAYER'S OWN
--       NAME COUNTS AS WORDS OF EVERY ROW IN IT here (decision 213, rule 5):
--       Santa Clara's 'Areas Closed to the Public' names an area, so its
--       polygon titled 'Summit Road' is a closed area like its 64 siblings.
--       A ROAD IN A WARNINGS LAYER IS A ROAD EVENT (decision 213's rule 8
--       refined, the poll of 2026-10-15, "Roads stay notices"): a row its
--       source files under warnings whose title, category or status names
--       a road ('road', 'hwy', a status's 'all-lanes-closed') and none of
--       them an area, a trail, a hiker's use or entry reads as a notice,
--       whatever its shape: NPS's 16 road lines ('Road Closed', 'Road
--       Closures in New Jersey', 'Akers Ferry Closure', all
--       'all-lanes-closed'; UA's notices.json of 2026-10-15 21:26 UTC and
--       the NPS feed read the same day). A closures-filed road line still
--       closes, as above.
--       AN ACTIVITY'S CLOSURE IS NOT THE TRAIL'S (the poll of 2026-10-15,
--       "Activity closures don't close"): a closing word directly after a
--       `names_an_activity` word (collection, collecting, fires, hunting,
--       shooting) in the same field closes that activity, so it is no
--       closing word at all: USFS R04's 'Spring Mountains National
--       Recreation Area Butterfly Collection Closure Area' is a notice. It
--       speaks again where the row's own narrative holds a closing word
--       that follows no activity: IATA's four 'Hunting Closure beginning …'
--       titles beside 'The Trail section … is closed Sept. 1 - Jan. 5 for
--       private hunting' still close (decision 213's rule 15). 'Camping'
--       is not listed: the seed reads it as a site already, to the same end
--       ('Tanque Verde Fall Camping Closure').
--       A STATUS SAYS NOTHING where it holds no word of the vocabulary but a
--       `stands` word (an on/off flag's yes: Active, Yes, 1) or an
--       `unspecified` one (-1, unknown), an empty status included. A value
--       no word reads ('Hazard', a workflow's 'Final') says nothing about a
--       closure, so the row's own title speaks, as decision 190's "else a
--       placed row's title" reads: King County's 'Cedar River Trail closed
--       due to flood damage …', AlertType 'Hazard', closes by its title. A
--       status that holds a word still speaks ('Closure with Detour' keeps
--       a title's 'closed' from closing). Until the review of 2026-10-15
--       (S1-1) a status no word read, and a blank status on a source that
--       states one on other rows (Missouri's, decision 164; 5 of
--       Yellowstone's bear management areas), kept the title from speaking.
--       A category holding any other word of the vocabulary still keeps the
--       title from speaking ('Alert', 'Planned', 'Partial'); until decision
--       213's rule 2 a restriction word did too, and USFS R04's 'Roaring
--       River & William Pogue NRT Trail Closure' was a notice.
--    d. A NOTICE nobody reviewed, otherwise (decision 7: miss rather than
--       cry wolf).
--    A HAZARD AREA (rule 6) is read by its hazard category alone, never by
--    the vocabulary: 'Open' on a shooting range is the hazard, not its
--    absence.
-- 3. A NOTICE CLOSES THE TRAIL BY ITS OWN WORDS, WHATEVER FILE ITS SOURCE IS
--    REGISTERED UNDER, AND NEVER ONCE ITS OWN END HAS PASSED (decision 213,
--    rule 8, the maintainer's poll of 2026-10-15: "a row's own words decide
--    whether it closes"). `obstructs_trail` is true only where rule 2 reads
--    `closes_trail`, nothing holds it, its own dates do not contradict each
--    other (rule 1, notice_dates_contradict()), and its own end day, a
--    season's where rule 1 reads one, is not more than
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
--    publishes only the rows whose own category names one of them: IATA's
--    'No hunting' parcels and NY Parks' safety zones are where hunting is
--    not allowed, and drawing one as a hunting area would tell a hiker the
--    opposite of what the layer says. The rest are held with the category
--    in the reason. A source listed with no category value publishes every
--    row. ONE STANDARD FOR EVERY HAZARD SOURCE (decision 190's "apply
--    standards across the orgs"), each value and each category read as
--    words, as rule 2 reads a field's (lowercase, every run of characters
--    that are not letters or digits one space, 'non' joined to the word
--    after it):
--    a. the category's own code, or its layer's label for the code
--       (seeds/notice_category_labels.csv, the label WHAT A ROW SHOWS
--       below), IS a listed value: IATA stages Hunting_Reg's code 'Open',
--       whose label is the listed 'Open for public hunting'. The whole
--       value is the seed's own reading of it, a negating word in it
--       included: USACE's 'Closed to Center-fire Rifles Only / Trapping by
--       Special Permit Only' is listed because only those rifles are barred;
--    b. or the code or the label HOLDS a listed value as whole words, and
--       none of the words that negate it ('no', 'not', 'prohibited',
--       'closed', below): a free-text field names its hazard among other
--       words, NY Parks' Description 'Big game deer hunting area.' holding
--       the listed 'Hunting area'. Whole words, so 'Non-hunting area' (one
--       word, 'nonhunting') and 'hunting areas' hold no 'hunting area'.
--    Until 2026-10-15 a category had to equal a listed value, case and
--    surrounding space aside, so IATA's 23 hunting parcels (staged as
--    codes the seed did not list) and all 134 of NY Parks' hunting areas
--    (24 wordings, none 'Hunting area' alone) were held and drawn as
--    nothing (read live that day).
--    Its dates are its own (`starts_on`, `ends_on`), and a layer with no
--    season field has none: none of the four hunting layers gives one
--    (seeds/notice_source_fields.csv), so their dates are null, never a
--    season OurHike supplied.
--
-- 7. STANDING CLOSED LAND HAS NO CLOCK (decision 213, rule 14, the
--    maintainer's poll of 2026-10-15; decision 156's reading of hazard areas
--    made general). `stands_until_lifted` is true on a row that closes the
--    trail (rule 3) where its own words say it is land closed until its
--    steward says otherwise rather than a dated event: an area (a Polygon or
--    a MultiPolygon, a point placed by its steward's area included) of a
--    full listing, served whole on every read, that closes by a state word
--    in its own status or category ('Closed', c1, never a category's
--    'closure', which names an event) or by its layer's own name (c3), and
--    that states no start, no end, no season and no end in its title.
--    pub_conditions_notices writes it no `current_until` and `standing` true,
--    and the phone reads "Closed until <steward> says otherwise." Midpen's
--    133 closed areas (status 'Closed', edited 2026-07-21 in one bulk
--    reload) and Santa Clara's 64 'Areas Closed to the Public' are such rows
--    on UA's notices.json of 2026-10-15 21:26 UTC, which greyed the 64 and
--    would have greyed the 133 on 2026-10-20. @unvalidated that a status
--    layer's 'Closed' stays true for as long as its steward serves it: a
--    steward who forgets a row leaves it closed on the phone, the side a
--    hiker is safer on.
--
-- `key_versions` is how many different raw rows share the notice's key (its
-- base model counts them); int_closures__gate holds a source with any over
-- one.
--
-- WHAT A ROW SHOWS (the review of PR #1805 of 2026-10-15, threads
-- 4279218690 and 4279219442). Its `category` is its layer's own label for
-- the code the category holds, where the layer's coded-value domain gives
-- one that differs (seeds/notice_category_labels.csv): Utah FFSL's
-- 'Prevention Order' shows as 'Fire Prevention Order', Wisconsin's
-- 'storm damage' as 'Storm damage'. The rules above read the code, which
-- the vocabulary's words were written against. A title that is only an
-- identifier, one word holding a digit ('UT914-25-001', 23 of FFSL's 24
-- rows on a phone, read live 2026-10-15), is named by that label wherever
-- the label holds a letter and the category is not the row's status again:
-- 'Fire Prevention Order UT914-25-001'. A status staged as the category
-- (decision 78, where nothing else says what a row is) names a state, not a
-- kind, so Region 8's burn block 'HS84-1', whose category is its
-- BURN_STATUS, keeps its identifier, as one with no category ('M08HBP01',
-- FLTC's hunting bypasses) or a category of no letters ('1.0') does: nothing
-- else on the row says what it is, and a layer's own name often says less
-- ('Locations').
--
-- `issuer` IS THE AGENCY THAT ISSUED A COMPILED LAYER'S ORDER (decision 213,
-- rule 21, the maintainer's poll of 2026-10-15), where the layer's rows name
-- it: the field seeds/notice_issuers.csv names, staged as `issuer` on that
-- source alone, shown by the label the layer's own domain gives its code
-- ('3-BLM' is 'Bureau of Land Management'), else as the row writes it
-- ('Boise National Forest'). Null on every other source. The phone's sheet
-- reads "<issuer> order, via <publisher>", so Utah FFSL keeps the credit its
-- terms ask for and the hiker learns whose order it is.
--
-- `updated_at` is the source's own edit stamp, in ISO 8601 UTC, and null
-- where it gives none: never the load time. `notice_id` is
-- `<source key>:<the source's own id>` (features/ORG_NOTICES.md section 2).
with unioned as (
    select * from {{ ref('int_closures__club_notices_unioned') }}
),

-- The label a layer's own coded-value domain gives a code its category
-- holds, where the two differ.
category_labels as (
    select
        source_key,
        code,
        label
    from {{ ref('notice_category_labels') }}
),

-- The label a compiled layer's own coded-value domain gives the code its
-- issuer field holds (seeds/notice_issuers.csv; decision 213, rule 21).
issuer_labels as (
    select
        source_key,
        code,
        label
    from {{ ref('notice_issuers') }}
    where coalesce(trim(code), '') != ''
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

-- Rule 2's `not_a_qualifier` phrases, one pattern per field: a qualifying
-- word inside one of them qualifies nothing ('closed until further
-- notice'). Every `words` row is lowercase letters and digits, one space
-- between (the seed's own test), so a phrase needs no escaping.
unqualifying as (
    select
        field,
        ' (?:' || string_agg(word, '|' order by word) || ') ' as pattern
    from words
    where reads_as = 'not_a_qualifier'
    group by field
),

-- AN ACTIVITY'S CLOSURE, one pattern per field (decision 213, the
-- maintainer's poll of 2026-10-15, "Activity closures don't close"): a
-- `names_an_activity` word directly before a `words` closing word ('Butterfly
-- Collection Closure', 'Hunting Closure') closes that activity, not the
-- trail. `activity_pattern` takes the closing word out and keeps the
-- activity; `phrase_pattern` finds the phrase, for `read_from`.
activity_words as (
    select
        field,
        string_agg(word, '|' order by word) as alternatives
    from words
    where reads_as = 'names_an_activity' and matches = 'words'
    group by field
),

closing_words as (
    select
        field,
        string_agg(word, '|' order by word) as alternatives
    from words
    where reads_as = 'closes_trail' and matches = 'words'
    group by field
),

activity_closures as (
    select
        activity_words.field,
        ' ((?:' || activity_words.alternatives || ') )(?:'
        || closing_words.alternatives || ') ' as activity_pattern,
        ' ((?:' || activity_words.alternatives || ') (?:'
        || closing_words.alternatives || ')) ' as phrase_pattern
    from activity_words
    inner join closing_words on activity_words.field = closing_words.field
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

field_words as (
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

-- `qualifier_value` is the padded value with its field's `not_a_qualifier`
-- phrases taken out, the value a qualifying word is looked for in;
-- `activity_value` the padded value with each activity's closing word taken
-- out, and `activity_phrase` the first such phrase ('collection closure').
field_text as (
    select
        field_words.*,
        case
            when unqualifying.pattern is null then field_words.padded_value
            else
                regexp_replace(
                    field_words.padded_value, unqualifying.pattern, ' ', 'g'
                )
        end as qualifier_value,
        case
            when activity_closures.activity_pattern is null
                then field_words.padded_value
            else
                regexp_replace(
                    field_words.padded_value,
                    activity_closures.activity_pattern,
                    ' \1',
                    'g'
                )
        end as activity_value,
        nullif(
            regexp_extract(
                field_words.padded_value,
                coalesce(activity_closures.phrase_pattern, '$^'),
                1
            ),
            ''
        ) as activity_phrase
    from field_words
    left join unqualifying on field_words.field = unqualifying.field
    left join activity_closures
        on field_words.field = activity_closures.field
),

-- A CLOSED SITE's title reading: each thing a title lists, the parts between
-- '&', '+', a comma, a slash, a spaced dash, 'and' or 'or'.
title_parts as (
    select
        notice_key,
        unnest(
            regexp_split_to_array(
                lower(title),
                '\s*(?:&|\+|,|/|\s[-–—]+\s|\band\b|\bor\b)\s*'
            )
        ) as item
    from notices
    where trim(coalesce(title, '')) != ''
),

-- Each listed thing padded as a field is; two equal parts of one title are
-- one thing.
title_items as (
    select distinct
        notice_key,
        ' ' || trim(
            regexp_replace(
                regexp_replace(item, '\bnon[^a-z0-9]+', 'non', 'g'),
                '[^a-z0-9]+',
                ' ',
                'g'
            )
        ) || ' ' as padded_item
    from title_parts
),

-- What each listed thing is: a site where a site word is the last of its
-- site and trail words, a trail where a trail word or a hiker's use is.
items_named as (
    select
        title_items.notice_key,
        title_items.padded_item,
        min(
            strpos(
                reverse(title_items.padded_item),
                reverse(' ' || words.word || ' ')
            )
        ) filter (where words.reads_as = 'a_site_not_the_trail') as site_end,
        min(
            strpos(
                reverse(title_items.padded_item),
                reverse(' ' || words.word || ' ')
            )
        ) filter (
            where words.reads_as in ('names_a_trail', 'a_hikers_use')
        ) as trail_end
    from title_items
    inner join words
        on
            words.field = 'title'
            and words.matches = 'words'
            and words.only_source is null
            and contains(title_items.padded_item, ' ' || words.word || ' ')
    where
        words.reads_as in (
            'a_site_not_the_trail', 'names_a_trail', 'a_hikers_use'
        )
    group by title_items.notice_key, title_items.padded_item
),

titles_named as (
    select
        notice_key,
        bool_or(site_end < coalesce(trail_end, 2147483647)) as lists_a_site,
        bool_or(trail_end < coalesce(site_end, 2147483647)) as lists_a_trail
    from items_named
    group by notice_key
),

-- Whether every status a source states is a `code` word or an `unspecified`
-- one (a coded flag, its -1 included).
source_statuses as (
    select
        notices.source_key,
        bool_and(
            trim(coalesce(notices.status, '')) = ''
            or lower(trim(notices.status)) in (
                select flags.word from words as flags
                where
                    flags.field = 'status'
                    and (
                        flags.matches = 'code'
                        or flags.reads_as = 'unspecified'
                    )
            )
        ) as states_only_codes
    from notices
    group by notices.source_key
),

-- Every word of the vocabulary each notice's fields hold, and for a `words`
-- match how far from the field's end its last occurrence ends (1 at the end),
-- so a title's last-named thing can be told from the others. A qualifying
-- word is looked for outside the field's `not_a_qualifier` phrases.
hits as (
    select
        field_text.notice_key,
        field_text.field,
        words.word,
        words.reads_as,
        words.outranks_status,
        words.category_needs_title,
        field_text.whole_value = words.word as is_whole_value,
        coalesce(
            words.reads_as = 'closes_trail'
            and words.matches = 'words'
            and not contains(
                field_text.activity_value, ' ' || words.word || ' '
            ),
            false
        ) as after_an_activity,
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
        words.reads_as != 'not_a_qualifier'
        and (
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
                and contains(
                    case
                        when
                            words.reads_as in (
                                'partly',
                                'a_way_around',
                                'not_a_closure',
                                'states_a_start'
                            )
                            then field_text.qualifier_value
                        else field_text.padded_value
                    end,
                    ' ' || words.word || ' '
                )
            )
        )
),

-- A ROW WHOSE OWN NARRATIVE CLOSES SOMETHING beyond an activity: there an
-- activity's closure in its title is the trail's too, IATA's 'Hunting
-- Closure beginning 9/1' beside 'The Trail section … is closed Sept. 1 -
-- Jan. 5 for private hunting' (live 2026-10-15). A narrative is prose, so
-- any closing word in it counts, whatever qualifies it.
narrative_closes as (
    select distinct notice_key
    from hits
    where
        field = 'narrative'
        and reads_as = 'closes_trail'
        and not after_an_activity
),

-- Every hit but an activity's closing word, unless the narrative closes.
kept_hits as (
    select hits.*
    from hits
    left join narrative_closes
        on hits.notice_key = narrative_closes.notice_key
    where not (hits.after_an_activity and narrative_closes.notice_key is null)
),

-- The activity's closure a row's words hold and kept from closing, for
-- `read_from`: its field and phrase.
activity_held as (
    select
        field_text.notice_key,
        min(
            field_text.field || ' ''' || trim(field_text.activity_phrase)
            || ''''
        ) as activity_from
    from field_text
    left join narrative_closes
        on field_text.notice_key = narrative_closes.notice_key
    where
        field_text.activity_phrase is not null
        and field_text.field != 'narrative'
        and narrative_closes.notice_key is null
    group by field_text.notice_key
),

-- What each field says, once per notice and field. A `partly`,
-- `a_way_around`, `not_a_closure` or `states_a_start` word qualifies a
-- closing word in the same field (`is_qualified`); in a title a start word
-- does only where the title states no day it starts (`read_words` below), so
-- the title's own flag leaves it out.
field_readings as (
    select
        notice_key,
        field,
        bool_or(
            reads_as in (
                'partly', 'a_way_around', 'not_a_closure', 'states_a_start'
            )
        ) as is_qualified,
        bool_or(
            reads_as in ('partly', 'a_way_around', 'not_a_closure')
        ) as is_qualified_but_for_a_start,
        min(word) filter (where reads_as = 'states_a_start') as start_word,
        bool_or(reads_as = 'not_a_closure') as says_not_a_closure,
        bool_or(reads_as = 'a_way_around') as names_a_way_around,
        bool_or(reads_as not in ('stands', 'unspecified')) as says_something,
        min(word) filter (where reads_as = 'closes_trail') as closing_word,
        min(word) filter (
            where reads_as = 'closes_trail' and not category_needs_title
        ) as closing_state_word,
        min(word) filter (
            where reads_as = 'closes_trail' and is_whole_value
        ) as whole_closing_word,
        bool_or(category_needs_title and reads_as = 'not_a_closure')
            as names_a_kind,
        bool_or(
            not category_needs_title
            and reads_as not in (
                'names_a_trail', 'names_a_road', 'names_an_area'
            )
        ) as says_more_than_a_kind,
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
        bool_or(reads_as in ('names_a_trail', 'a_hikers_use'))
            as names_a_trail,
        min(word) filter (where reads_as = 'names_a_road') as road_word,
        bool_or(reads_as = 'names_an_area') as names_an_area,
        bool_or(reads_as = 'stands') as stands,
        bool_or(reads_as = 'unspecified') as unspecified
    from kept_hits
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
            min('title ''' || road_word || '''') filter (where field = 'title'),
            min('category ''' || road_word || '''')
            filter (where field = 'category'),
            min('status ''' || road_word || '''')
            filter (where field = 'status')
        ) as any_road_from,
        coalesce(
            bool_or(names_an_area)
            filter (where field in ('title', 'category', 'layer')),
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
        min('category ''' || whole_closing_word || '''')
        filter (where field = 'category') as category_whole_closes_from,
        coalesce(
            bool_or(closing_outranks) filter (
                where field in ('status', 'category') and not is_qualified
            ),
            false
        ) as closing_outranks,
        min('title ''' || closing_word || '''')
        filter (where field = 'title' and not is_qualified_but_for_a_start)
            as title_closing_word_from,
        min(start_word) filter (where field = 'title') as title_start_word,
        coalesce(
            bool_or(says_not_a_closure or names_a_way_around)
            filter (where field = 'title'),
            false
        ) as title_says_not_a_closure,
        coalesce(
            bool_or(names_a_way_around and closing_word is null)
            filter (where field = 'layer'),
            false
        ) as layer_is_a_way_around,
        coalesce(
            bool_or(says_something) filter (where field = 'status'), false
        ) as status_says_something,
        coalesce(bool_or(stands) filter (where field = 'status'), false)
            as status_stands,
        coalesce(bool_or(unspecified) filter (where field = 'status'), false)
            as status_unspecified,
        coalesce(
            bool_or(not_a_hikers_use_word is not null)
            filter (where field = 'status'),
            false
        ) as status_names_a_use_hikers_are_not,
        coalesce(bool_or(field = 'category'), false) as category_holds_a_word,
        coalesce(
            bool_or(says_more_than_a_kind or not names_a_kind)
            filter (where field = 'category'),
            false
        ) as category_keeps_the_title_quiet
    from field_readings
    group by notice_key
),

-- Rule 6's seed: each hazard source once, with whether every row is the
-- hazard.
hazard_sources as (
    select
        source_key,
        any_value(hazard) as hazard,
        bool_or(coalesce(trim(category_value), '') = '') as every_row
    from {{ ref('notice_hazard_areas') }}
    group by source_key
),

-- Rule 6's listed values, each as words, padded with a space each side.
hazard_values as (
    select distinct
        source_key,
        ' ' || trim(
            regexp_replace(
                regexp_replace(
                    lower(category_value), '\bnon[^a-z0-9]+', 'non', 'g'
                ),
                '[^a-z0-9]+',
                ' ',
                'g'
            )
        ) || ' ' as value_words
    from {{ ref('notice_hazard_areas') }}
    where coalesce(trim(category_value), '') != ''
),

-- What rule 6 reads of the category of a source listed with category
-- values: the code a row holds, and its layer's own label for that code.
hazard_category_texts as (
    select
        notices.notice_key,
        notices.source_key,
        notices.category as category_text
    from notices
    inner join hazard_sources
        on
            notices.source_key = hazard_sources.source_key
            and not hazard_sources.every_row
    union all
    select
        notices.notice_key,
        notices.source_key,
        category_labels.label as category_text
    from notices
    inner join hazard_sources
        on
            notices.source_key = hazard_sources.source_key
            and not hazard_sources.every_row
    inner join category_labels
        on
            notices.source_key = category_labels.source_key
            and notices.category = category_labels.code
),

-- Each as words, with the first of the words that negate a hazard it holds
-- inside a longer value: 'no', 'not', 'prohibited' and 'closed', the
-- smallest set that reads 'No hunting', 'hunting not permitted', 'hunting
-- prohibited' and 'closed to hunting' (Reasoned from those wordings). The
-- vocabulary has no such reading to borrow: its `not_a_closure` words would
-- negate the hunting they qualify, 'only' in NY Parks' 'Big game deer bow
-- only hunting area.' and IATA's 'Open for deer hunting by permit only',
-- 'restricted' and 'limited' wherever a weapon is. A negating word anywhere
-- in the value counts, so a 'Hunting area. No ATVs.' would be held: a miss
-- rather than a no-hunting parcel drawn as hunting, the side rule 6 already
-- errs on. No live row holds a listed value inside a longer value beside
-- one of the four (read 2026-10-15: NY Parks' 134 wordings, the rest
-- equal a listed value or hold none).
hazard_category_words as (
    select
        notice_key,
        source_key,
        padded as text_words,
        nullif(
            regexp_extract(padded, ' (no|not|prohibited|closed) ', 1), ''
        ) as negating_word
    from (
        select
            notice_key,
            source_key,
            ' ' || trim(
                regexp_replace(
                    regexp_replace(
                        lower(category_text), '\bnon[^a-z0-9]+', 'non', 'g'
                    ),
                    '[^a-z0-9]+',
                    ' ',
                    'g'
                )
            ) || ' ' as padded
        from hazard_category_texts
        where trim(coalesce(category_text, '')) != ''
    ) as texts
),

-- Each row of a source listed with category values against each value its
-- source lists: whether its code or its label is the value (a), and whether
-- it holds the value as whole words.
hazard_matches as (
    select
        hazard_category_words.notice_key,
        hazard_category_words.negating_word,
        hazard_category_words.text_words = hazard_values.value_words
            as is_listed,
        contains(
            hazard_category_words.text_words, hazard_values.value_words
        ) as holds_listed
    from hazard_category_words
    inner join hazard_values
        on hazard_category_words.source_key = hazard_values.source_key
),

-- Rule 6's reading of each such row: its category names the hazard where
-- its code or its label is a listed value (a), or holds one as whole words
-- beside no negating word (b); `negated_by` is the negating word where one
-- kept a listed value the row holds from counting.
hazard_categories as (
    select
        notice_key,
        bool_or(is_listed or (holds_listed and negating_word is null))
            as names_the_hazard,
        min(negating_word) filter (where holds_listed and not is_listed)
            as negated_by
    from hazard_matches
    group by notice_key
),

-- Each notice with its own dates (rule 1), the day its title says it starts
-- (rule 2's c2) and its season, where its own words state one (rule 1).
dated as (
    select
        notices.*,
        cast(timezone('UTC', notices.starts_at) as date) as own_starts_on,
        cast(timezone('UTC', notices.ends_at) as date) as own_ends_on,
        cast(timezone('UTC', notices.rescinded_at) as date) as rescinded_on,
        {{ notice_build_date() }} as build_date,
        {{ notice_title_start_day(
            'notices.title',
            'said.title_start_word',
            "coalesce(cast(timezone('UTC', notices.starts_at) as date), "
            ~ "cast(timezone('UTC', notices.source_edited_at) as date))"
        ) }} as title_starts_on,
        {{ notice_title_end_day('notices.title') }} as title_ends_on
    from notices
    left join said on notices.notice_key = said.notice_key
),

season_parts as (
    select
        *,
        {{ notice_season_part('season', 'start_month') }} as season_start_month,
        {{ notice_season_part('season', 'start_day') }} as season_start_day,
        {{ notice_season_part('season', 'end_month') }} as season_end_month,
        {{ notice_season_part('season', 'end_day') }} as season_end_day
    from dated
),

seasons as (
    select
        * exclude (
            season_start_month,
            season_start_day,
            season_end_month,
            season_end_day
        ),
        {{ notice_season_day(
            'season_start_month', 'season_start_day', 'season_end_month',
            'season_end_day', 'build_date', 'start'
        ) }} as season_starts_on,
        {{ notice_season_day(
            'season_start_month', 'season_start_day', 'season_end_month',
            'season_end_day', 'build_date', 'end'
        ) }} as season_ends_on
    from season_parts
),

-- Each notice with what its words say (rule 2), its hazard (rule 6) and its
-- dates (rule 1): a season where it states one and its own end has passed,
-- or it states none.
read_words as (
    select
        seasons.*,
        case
            when
                seasons.season_starts_on is not null
                and (
                    seasons.own_ends_on is null
                    or {{ notice_has_ended(
                        'seasons.own_ends_on', 'seasons.build_date'
                    ) }}
                )
                then seasons.season_starts_on
            else seasons.own_starts_on
        end as stated_starts_on,
        greatest(
            case
                when
                    seasons.season_starts_on is not null
                    and (
                        seasons.own_ends_on is null
                        or {{ notice_has_ended(
                            'seasons.own_ends_on', 'seasons.build_date'
                        ) }}
                    )
                    then seasons.season_ends_on
                else seasons.own_ends_on
            end,
            seasons.title_ends_on
        ) as ends_on,
        said.not_current_from,
        said.not_a_hikers_use_from,
        -- A title's closing word, where no start word qualifies it or the
        -- title states the day it starts.
        case
            when
                said.title_start_word is null
                or seasons.title_starts_on is not null
                then said.title_closing_word_from
        end as title_closes_from,
        coalesce(said.bars_every_use, false) as bars_every_use,
        coalesce(said.names_a_hikers_use, false) as names_a_hikers_use,
        case
            when coalesce(said.bars_every_use, false) then null
            when
                coalesce(titles_named.lists_a_site, false)
                and not coalesce(titles_named.lists_a_trail, false)
                then said.title_site_from
            when said.type_site_from is not null then said.type_site_from
            when
                trim(coalesce(seasons.site_type, '')) != ''
                and not coalesce(said.type_names_a_trail, false)
                and not coalesce(said.names_a_trail, false)
                then 'site_type ''' || lower(trim(seasons.site_type)) || ''''
            when
                said.kind_site_from is not null
                and not coalesce(said.type_names_a_trail, false)
                and not coalesce(said.names_a_trail, false)
                then said.kind_site_from
        end as site_from,
        coalesce(
            json_extract_string(seasons.geom_geojson, '$.type')
            in ('Polygon', 'MultiPolygon')
            and said.road_from is not null
            and not said.names_an_area
            and not said.names_a_trail
            and not said.bars_every_use,
            false
        ) as area_names_only_a_road,
        said.road_from,
        -- Decision 213's rule 8 refined (the poll of 2026-10-15, "Roads stay
        -- notices"): a warnings-filed row whose title, category or status
        -- names a road and none of them an area, a trail, a hiker's use or
        -- entry is a road event, never the trail, whatever its shape.
        coalesce(
            seasons.notice_type = 'warnings'
            and said.any_road_from is not null
            and not said.names_an_area
            and not said.names_a_trail
            and not said.bars_every_use,
            false
        ) as warning_names_only_a_road,
        said.any_road_from,
        activity_held.activity_from,
        said.layer_closes_from,
        said.closes_from as status_closes_from,
        said.category_kind_from,
        said.category_whole_closes_from,
        coalesce(said.closing_outranks, false) as closing_outranks,
        coalesce(said.title_says_not_a_closure, false)
        or (
            said.title_start_word is not null
            and seasons.title_starts_on is null
        ) as title_says_not_a_closure,
        coalesce(said.status_says_something, false) as status_says_something,
        coalesce(said.layer_is_a_way_around, false) as layer_is_a_way_around,
        coalesce(said.status_stands, false) as status_stands,
        coalesce(said.status_names_a_use_hikers_are_not, false)
            as status_names_a_use_hikers_are_not,
        coalesce(said.category_holds_a_word, false) as category_holds_a_word,
        coalesce(said.category_keeps_the_title_quiet, false)
            as category_keeps_the_title_quiet,
        (
            trim(coalesce(seasons.status, '')) = ''
            or coalesce(said.status_unspecified, false)
        ) as status_is_blank,
        seasons.geom_geojson is not null as is_placed,
        hazard_sources.hazard,
        coalesce(hazard_sources.every_row, false) as hazard_every_row,
        coalesce(hazard_categories.names_the_hazard, false)
            as hazard_category_listed,
        hazard_categories.negated_by as hazard_negated_by
    from seasons
    left join said on seasons.notice_key = said.notice_key
    left join titles_named on seasons.notice_key = titles_named.notice_key
    left join activity_held on seasons.notice_key = activity_held.notice_key
    left join hazard_sources
        on seasons.source_key = hazard_sources.source_key
    left join hazard_categories
        on seasons.notice_key = hazard_categories.notice_key
),

-- The closing word rule 2's c1 reads: its status's or its category's, a
-- category's 'closure' only beside its title's, which then closes by the
-- title's own words (`closes_by_title`).
closing as (
    select
        *,
        coalesce(
            status_closes_from,
            case when is_placed then category_whole_closes_from end,
            case
                when title_closes_from is not null
                    then category_kind_from || ' with its ' || title_closes_from
            end
        ) as closes_from,
        status_closes_from is null
        and category_kind_from is not null
        and title_closes_from is not null as closes_by_title
    from read_words
),

-- Rule 2's readings, the first that holds: which one, as a short name.
-- A status says nothing where it holds no word of the vocabulary but a
-- flag's yes or a coded unknown; a status says something else (rule b)
-- where it is neither blank, a flag's yes, nor itself a use a hiker is not.
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
                not status_says_something
                and not category_keeps_the_title_quiet
                and is_placed
                and title_closes_from is not null
                and site_from is not null
                then 'site'
            when
                not status_says_something
                and not category_holds_a_word
                and is_placed
                and site_from is not null
                then 'site'
            when
                not status_says_something
                and not category_keeps_the_title_quiet
                and is_placed
                and title_closes_from is not null
                and not layer_is_a_way_around
                then 'c2'
            when
                not status_says_something
                and not category_holds_a_word
                and is_placed
                and layer_closes_from is not null
                and not title_says_not_a_closure
                then 'c3'
            else 'd'
        end as reading_rule
    from closing
),

-- A row that closes by its title's words (c2, c3, or c1 where a category's
-- 'closure' needs the title) reads a start the title states as the day the
-- closure starts, the later of it and the row's own; then rule 1's date
-- tests.
started as (
    select
        *,
        case
            when
                (
                    reading_rule in ('c2', 'c3')
                    or (reading_rule = 'c1' and closes_by_title)
                )
                and title_starts_on is not null
                then greatest(
                    coalesce(stated_starts_on, title_starts_on),
                    title_starts_on
                )
            else stated_starts_on
        end as starts_on
    from ruled
),

-- Rule 1's one date hold comes last, from macros/notice_date_holds.sql;
-- rule 3's end date is `has_ended`, and its contradiction test
-- `dates_contradict`, which hold nothing back.
judged as (
    select
        *,
        case
            when reading_rule = 'a' then 'not_current'
            when reading_rule = 'b' then 'nothing_for_a_hiker'
            when
                reading_rule in ('c1', 'c2', 'c3')
                and (area_names_only_a_road or warning_names_only_a_road)
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
            when
                reading_rule in ('c1', 'c2', 'c3') and warning_names_only_a_road
                then any_road_from || ', a road and not the trail'
            when reading_rule = 'c1' then closes_from
            when reading_rule = 'c2' then title_closes_from
            when reading_rule = 'c3' then layer_closes_from
            when reading_rule = 'site'
                then site_from || ', a site and not the trail'
            when reading_rule = 'd' and activity_from is not null
                then
                    activity_from
                    || ', an activity''s closure and not the trail'
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
                and hazard_negated_by is not null
                then
                    'its own category, ' || category
                    || ', holds what notice_hazard_areas reads as ' || hazard
                    || ' beside ''' || hazard_negated_by
                    || ''', which negates it'
            when
                hazard is not null
                and not hazard_every_row
                and not hazard_category_listed
                then
                    'its own category, ' || coalesce(category, 'none')
                    || ', is not one notice_hazard_areas reads as '
                    || hazard
            when
                season_starts_on is not null
                and starts_on
                > build_date + {{ var('notice_season_lead_days') }}
                then
                    'its season starts on ' || starts_on || ', more than '
                    || '{{ var('notice_season_lead_days') }} days after this '
                    || 'build: a recurring season publishes from that many '
                    || 'days before it starts (decision 213, rule 9)'
            {{ notice_date_holds('build_date', 'rescinded_on') }}
        end as held_because,
        {{ notice_has_ended('ends_on', 'build_date') }} as has_ended,
        {{ notice_dates_contradict('starts_on', 'ends_on') }}
            as dates_contradict
    from started
),

-- Rule 3's verdict, for every notice whatever file its source is filed
-- under (decision 213, rule 8); then rule 7's standing closed land.
closes as (
    select
        *,
        coalesce(
            reads_as = 'closes_trail'
            and held_because is null
            and not has_ended
            and not dates_contradict,
            false
        ) as closes_the_trail
    from judged
),

stands as (
    select
        *,
        closes_the_trail
        and listing = 'full'
        and json_extract_string(geom_geojson, '$.type')
        in ('Polygon', 'MultiPolygon')
        and (
            (reading_rule = 'c1' and status_closes_from is not null)
            or reading_rule = 'c3'
        )
        and starts_on is null
        and ends_on is null
        and season_starts_on is null as stands_until_lifted
    from closes
),

-- What a row shows as its category: its layer's own label for the code;
-- and who issued it, where its layer compiles other agencies' orders.
shown as (
    select
        stands.*,
        coalesce(category_labels.label, stands.category) as category_label,
        coalesce(issuer_labels.label, nullif(trim(stands.issuer), ''))
            as issued_by
    from stands
    left join category_labels
        on
            stands.source_key = category_labels.source_key
            and stands.category = category_labels.code
    left join issuer_labels
        on
            stands.source_key = issuer_labels.source_key
            and stands.issuer = issuer_labels.code
)

select
    source_key || ':' || coalesce(source_id, 'key-' || notice_key) as notice_id,
    notice_key as source_row_key,
    'club_' || reader as notice_kind,
    club,
    source_key,
    notice_type,
    listing,
    case when closes_the_trail then true end as obstructs_trail,
    case
        when closes_the_trail then 'org_published' else 'not_reviewed'
    end as review_state,
    stands_until_lifted,
    case
        when
            regexp_full_match(trim(title), '\S*[0-9]\S*')
            and regexp_matches(category_label, '[A-Za-z]')
            and (status is null or category != status)
            then category_label || ' ' || trim(title)
        else {{ python_html_unescape('title') }}
    end as title,
    category_label as category,
    issued_by as issuer,
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
from shown
