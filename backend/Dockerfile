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

# Run as an unprivileged account (#1358). Nothing this process does needs
# root: no module under app/ writes to the filesystem (photos go to R2
# through a presigned URL), and uvicorn binds $PORT, which is above 1024 on
# every host this image targets - 8000 below, 10000 on Render. A dedicated
# account rather than `nobody`, which is shared with every other
# unprivileged process in the image and is not a boundary between them.
#
# The copied files stay root-owned and world-readable, deliberately: the app
# only ever reads them, so a process that cannot overwrite its own code is
# the stronger arrangement. The one thing that costs is bytecode caching -
# CPython would try to write __pycache__/ beside these files and silently
# carry on when it cannot, so the next line makes that a decision rather
# than a failure nobody sees. Dependencies in site-packages were already
# compiled during the pip layer above, while this was still running as root.
RUN useradd --system --no-create-home --shell /usr/sbin/nologin ourhike
ENV PYTHONDONTWRITEBYTECODE=1
USER ourhike

# Most PaaS hosts inject PORT at runtime rather than trusting a fixed value
# baked into the image - default to 8000 for any host/local run that doesn't
# set it. This one line is what makes the image portable across Render,
# Railway, Koyeb, Cloud Run and the rest, which is why there is no
# host-specific config file beside it (see HOSTING.md).
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
