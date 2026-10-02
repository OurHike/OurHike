-- The NBM weather squares under a trail or a waypoint
-- (build_weather_squares.py's choice, the maintainer's of 2026-09-24): one
-- row per square, however many trail cells list it, as
-- export_weather_alerts.py's bake() reads them into `trail`, the set an
-- alert's polygon is tested against (WN03). A square is (row, col) on NOAA's
-- NBM CONUS grid, and covers the box (col, row) to (col + 1, row + 1) in grid
-- units (lib/nbm_grid.py).
with squares_documents as (
    select * from {{ ref('stg_derived__weather_squares') }}
),

-- The document is read once, as a map from cell to its squares: a JSON path
-- per cell re-reads the whole document for each one, which took 34 s on a
-- 26,103-square document (measured 2026-10-02, DuckDB 1.5.5).
cells as (
    select
        release,
        unnest(map_values(cast(
            json_extract(squares_document, '$.cells')
            as map (varchar, integer[][])
        ))) as cell_squares
    from squares_documents
),

listed as (
    select
        release,
        unnest(cell_squares) as square
    from cells
),

squares as (
    select distinct
        release as squares_release,
        square[1] as square_row,
        square[2] as square_col
    from listed
)

select
    {{ dbt_utils.generate_surrogate_key([
        'squares_release', 'square_row', 'square_col',
    ]) }} as weather_square_key,
    squares_release,
    square_row,
    square_col
from squares
