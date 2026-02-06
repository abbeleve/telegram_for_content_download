FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock* ./
ENV UV_NO_DEV=1

RUN uv sync --locked

COPY . .


CMD ["uv", "run", "main.py"]