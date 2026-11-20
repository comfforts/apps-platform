ARG UV_IMAGE=ghcr.io/astral-sh/uv@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1
ARG PYTHON_BUILD_IMAGE=python@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ARG PYTHON_RUNTIME_IMAGE=python@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_BUILD_IMAGE} AS build

COPY --from=uv /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /srv/app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

FROM ${PYTHON_RUNTIME_IMAGE}

ENV PATH=/srv/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /srv/app
COPY --from=build /srv/app/.venv /srv/app/.venv
COPY contracts ./contracts
COPY edge ./edge
USER 65532:65532
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "edge.live:create_live_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
