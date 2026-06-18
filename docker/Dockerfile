FROM python:3.12-slim

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY . /app

ENV UV_NO_DEV=1

WORKDIR /app

RUN uv sync --locked
RUN chmod +x /app/docker/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["serve"]
