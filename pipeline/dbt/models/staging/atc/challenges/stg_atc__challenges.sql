-- The ATC's challenge files in the shape every club's challenges take
-- (stg_<club>__challenges, CH01): the folder that extracted them, the claim
-- they were landed under, and the file's folder and name, which
-- export_challenges.py checks against the file's own `org` and `id`.
-- Renames only: the gate is int_challenges__files.
--
-- `file_folder` is the path's last directory and `file_name` its last part,
-- as pathlib's `path.parent.name` and `path.name` read them; `file_stem` is
-- `path.stem`, the name less its one `.json`.
with files as (
    select * from {{ ref('base_atc__challenges_atc') }}
)

select
    challenge_file_key,
    'atc' as club,
    'reference/challenges/atc' as source_key,
    file_path,
    regexp_extract(file_path, '([^/]+)/[^/]+$', 1) as file_folder,
    regexp_extract(file_path, '([^/]+)$', 1) as file_name,
    regexp_extract(file_path, '([^/]+)\.json$', 1) as file_stem,
    file_json,
    file_json_text,
    parse_error,
    _loaded_at
from files
