# AIPI API image.
#
# Playwright and the scraping stack are deliberately NOT installed here. The API
# serves an already-computed index; it never scrapes. Keeping the browser out of
# this image keeps it small and means the internet-facing service has no
# automation capability it does not need.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependency layer first so application edits do not invalidate the install.
COPY pyproject.toml README.md ./
COPY aipi/__init__.py ./aipi/__init__.py
RUN pip install --no-cache-dir -e "." && pip install --no-cache-dir "pytest>=8.2"

COPY aipi ./aipi
COPY scripts ./scripts
COPY dashboard ./dashboard
COPY data/reference ./data/reference
COPY tests ./tests

EXPOSE 8000

# Run as an unprivileged user: this process serves the public API and has no
# reason to hold root inside the container.
RUN useradd --create-home --uid 10001 aipi && chown -R aipi:aipi /app
USER aipi

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "aipi.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
