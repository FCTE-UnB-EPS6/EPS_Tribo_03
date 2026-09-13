FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt \
    && groupadd --gid 10001 esg \
    && useradd --uid 10001 --gid esg --no-create-home esg
COPY app/ ./app/
COPY config/ ./config/
COPY migrations/ ./migrations/
COPY examples/ ./examples/
COPY scripts/ ./scripts/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=15s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
USER root
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
COPY tests/ ./tests/
USER 10001:10001
HEALTHCHECK NONE
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
