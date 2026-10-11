# syntax=docker/dockerfile:1

# ---- build: resolve and install the locked dependencies into /opt/venv ----
FROM python:3.13-slim AS builder
RUN pip install --no-cache-dir "uv>=0.5"
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

# ---- runtime: no compilers, no uv, non-root ----
FROM python:3.13-slim
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin flowtask
COPY --from=builder /opt/venv /opt/venv
WORKDIR /srv
COPY app ./app
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0555 /usr/local/bin/entrypoint.sh
USER flowtask
EXPOSE 8000
# /ready also checks the database, so an unhealthy container is one that cannot serve users
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3).status == 200 else 1)"
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
