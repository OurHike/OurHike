-- The states and equivalents as the rest of the project reads them: the
-- two-letter code, the name and the shape, from the Census Bureau's
-- TIGER/Line file (base_census__census_tiger_states). Nothing is filtered;
-- int_closures__notice_state_shapes picks the states a notice names.
select
    stusps as state,
    name as state_name,
    geom,
    _loaded_at
from {{ ref('base_census__census_tiger_states') }}
