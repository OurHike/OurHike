-- Every club's challenge files, one row per file, by name and never by
-- position (pipeline/ELT.md, "Layers and naming"). One branch today: the ATC
-- is the only club with a challenges resource (extract/atc/challenges.py).
-- A club that adds one adds its stg_<club>__challenges here.
--
-- export_challenges.py globs every folder under reference/challenges/ in one
-- pass; here each club's folder is its own claim, so a folder no club file
-- claims is not read at all, where today's exporter would read it. None
-- exists on 2026-10-02 (atc/ is the only one).
select * from {{ ref('stg_atc__challenges') }}
