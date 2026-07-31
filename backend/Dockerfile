# Production image for the OurHike FastAPI backend.
#
# Migrations are deliberately NOT run automatically on container start -
# `alembic upgrade head` is a separate, reviewed step (see README.md), not
# something that fires unattended on every deploy/restart. A bad migration
# should never be able to block the app from starting, and multiple
# instances starting simultaneously should never race on schema changes.
#
# Matches the Python version pinned in .github/workflows/backend-tests.yml
# and pipeline-tests.yml, so local/CI/production all run the same interpreter.
FROM python:3.14-slim

WORKDIR /app

# Install dependencies first, separately from app code, so this layer only
# rebuilds when requirements.txt actually changes - not on every code edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Cloudflare/most PaaS hosts (Fly.io included) inject PORT at runtime rather
# than trusting a fixed value baked into the image - default to 8000 for
# any host/local run that doesn't set it.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
