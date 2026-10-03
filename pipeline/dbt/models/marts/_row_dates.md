{% docs row_first_seen_at %}
When this row's key was first seen in this mart, in UTC: the earliest
dbt_valid_from of the key in the mart's row-history snapshot,
int_<mart>__history (macros/row_history.sql). The row appeared at or before
this time and after the build before it. **Where this equals the snapshot's
history start** (its earliest dbt_valid_from, which the history store's
history.json records), the row was already there when history began, so the
value is a bound, not a date: first published at or before then, possibly
long before. Null only in a build whose history could not be restored, where
it means unknown, never new.
{% enddocs %}

{% docs row_changed_at %}
When this row last changed, in UTC: the build whose snapshot first held its
current content, compared by `_row_hash`, a hash of every contracted column
but `_loaded_at` (macros/row_hash.sql). A change to a field the mart does not
carry moves nothing. The change happened at or before this time and after
the build before it; a row unchanged since history began reads the history
start. Null only in a build whose history could not be restored.
{% enddocs %}

{% docs row_history_snapshot %}
The mart's row history (decision 57): every version of every row of
int_<mart>__final, whole, with `_row_hash` (what the check strategy
compares), `_built_by` (the commit and workflow run that wrote the version,
never hashed) and dbt's validity columns. A row that leaves the mart keeps
its last version with dbt_valid_to set; macros/row_history.sql's
row_history_removed() reads those back, for the later decision on merging
removed features. Kept between runs outside the warehouse: build_marts.py
restores it from the history store (--history-url, else OURHIKE_HISTORY_URL)
before dbt runs and saves it back only after the whole build succeeds with
its history (pipeline/row_history.py).
{% enddocs %}
