# CheMTlab backend image (API + Celery worker share this image)
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 postgresql-client libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 chemtlab

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project --no-dev $( [ -f uv.lock ] && echo --frozen )

COPY . .
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && mkdir -p /data/media /app/staticfiles \
    && chown -R chemtlab:chemtlab /data /app/staticfiles

USER chemtlab
ENV CHEMTLAB_MEDIA_ROOT=/data/media
EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "chemtlab.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
