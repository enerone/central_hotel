FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

FROM base AS deps
COPY pyproject.toml .
# Non-editable install for Docker layer caching — only needs pyproject.toml
RUN pip install ".[dev]"

FROM deps AS app
EXPOSE 8000
COPY . .
# No --reload here; added as override in docker-compose.yml for dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
