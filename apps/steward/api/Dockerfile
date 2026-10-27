# Campsite Steward's API (#1906). backend/Dockerfile's shape, for its reasons:
# migrations are a separate reviewed step, never run on start; an unprivileged
# user; PORT from the environment, so the same image runs on Render (the host
# backend/HOSTING.md chose for OurHike's API) or anywhere else.
FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY steward_api/ ./steward_api/
COPY alembic/ ./alembic/
COPY alembic.ini .

RUN useradd --system --no-create-home --shell /usr/sbin/nologin steward
ENV PYTHONDONTWRITEBYTECODE=1
# glibc keeps memory a thread freed in that thread's own arena, and photos are
# re-encoded on the threadpool's threads. Eight 2048 x 2048 photos at once
# (photos.reencode, two decoding at a time) raised the process by 137 MB, and
# by 71 MB with two arenas: measured 2026-10-27 in the build sandbox, not on
# the host, after the adversarial review's third pass found the same effect.
ENV MALLOC_ARENA_MAX=2
USER steward

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn steward_api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
