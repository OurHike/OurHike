"""Stand-ins for the dbt_utils macros the models call, for SQLFluff only.

SQLFluff lints with its jinja templater (pipeline/.sqlfluff), which renders
`{{ ... }}` without dbt. `ref`, `source` and `config` come from the
templater's own dbt builtins; a package macro does not, so each one a model
calls needs a function here or the file fails to render. `library_path` in
pipeline/.sqlfluff names this directory, and this module becomes the
`dbt_utils` namespace.

These are not the real macros and do not try to be. The lint only has to
see an SQL expression where the call sits; what the real macro compiles to
is checked by `dbt build` on the fixtures, which runs the real one. Add a
function here when a model starts calling another dbt_utils macro - lint
names the missing one ("Undefined jinja template variable").
"""


def generate_surrogate_key(field_list):
    """dim_pois.sql's poi_key. The real macro hashes each field cast to text,
    nulls coalesced, joined with '-'; md5 of a concatenation is the same
    shape of expression."""
    return "md5(" + " || '-' || ".join(f"cast({field} as varchar)" for field in field_list) + ")"
