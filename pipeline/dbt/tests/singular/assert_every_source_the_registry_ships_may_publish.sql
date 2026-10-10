-- A source sources.json ships (`reaches_hikers` true) that may_publish holds
-- back is a contradiction, and the build stops on it rather than publish
-- around it: either the registry row is wrong or the rule is, and which one
-- is a person's call. Holding it here also keeps int_sources__publication
-- from taking a layer off phones silently. On the registry at this commit
-- every one of the 59 shipping sources rests on `stated_by_org` or
-- `maintainer_authorisation` (counted 2026-10-02), both of which rule 1
-- admits, so this returns no rows.
select
    source_key,
    licence_basis,
    publication_rule
from {{ ref('sources', v=1) }}
where reaches_hikers and not may_publish
