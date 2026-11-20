ARG UV_IMAGE
FROM ${UV_IMAGE} AS uv

ARG PYTHON_BUILD_IMAGE
FROM ${PYTHON_BUILD_IMAGE} AS build

COPY --from=uv /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /srv/app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

ARG PYTHON_RUNTIME_IMAGE
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
