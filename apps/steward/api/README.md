# Campsite Steward API

Sign-in, saved lists with share links, and club ranking weights with history:
phase 2 of [`../PLAN.md`](../PLAN.md) (#1906). PLAN.md is the one home for what
this is and why; this file says only how to run it.

```
pip install -r requirements-dev.txt
python -m pytest                      # needs the local Postgres: backend/scripts/local-postgres.sh
STEWARD_DATABASE_URL=... python -m alembic upgrade head
STEWARD_SUPABASE_URL=https://<project>.supabase.co \
STEWARD_ALLOWED_ORIGINS=http://localhost:5173 \
STEWARD_SUMMARY_URL=https://<steward site>/data/summary.json \
  uvicorn steward_api.main:app --reload
```

Every setting is in `steward_api/config.py`, and every size and count it
enforces is in `steward_api/limits.py`.
