# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Hotel management SaaS platform. Hotel owners register, configure their property (rooms, services, promotions), and get an embeddable booking widget for their guests. Refer to `docs/superpowers/specs/` for the full design spec once written.

## Environment

```bash
source venv/bin/activate  # activate Python virtualenv before running anything
```

## Stack

FastAPI + Jinja2 + Alpine.js + HTMX + Vue 3 | PostgreSQL 16 + Redis | Celery | Docker Compose | Stripe | Resend

## Common Commands

```bash
source venv/bin/activate

# Run tests
pytest

# Run single test
pytest tests/core/test_health.py::test_health_returns_ok -v

# Start services
docker compose up app db redis -d

# Alembic
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Architecture

Modular monolith: `app/core/` (config, DB, base models) + domain modules (`auth/`, `hotels/`, `bookings/`, `extras/`, `billing/`, `widget/`, `notifications/`, `superadmin/`).

Tests use real PostgreSQL (`hotel_test` DB), per-test transaction rollback via SQLAlchemy 2.x `join_transaction_mode="create_savepoint"`. No DB mocking.

See `docs/superpowers/specs/2026-03-14-hotel-saas-design.md` for full design spec.
See `docs/superpowers/plans/` for implementation plans.
