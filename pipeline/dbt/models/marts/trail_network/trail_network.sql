-- The trail network mart (decision 57): int_trail_network__final's rows as
-- int_trail_network__history holds them now, each with when it was first seen
-- and when it last changed (macros/row_history.sql). A row that left the mart
-- stays in the snapshot, closed, and is not here: how removed features merge
-- back is a later decision, and row_history_removed() is its hook. With
-- OURHIKE_ROW_HISTORY=off, both dates are null.
{{ row_history_mart(
    'int_trail_network__history', 'int_trail_network__final', 'edge_id'
) }}
