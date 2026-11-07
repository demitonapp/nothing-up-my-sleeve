# Thorp: the backend

The Python package (`thorp/`), its tests, scripts and the Alembic migrations of the Postgres fitout store.
The project, the dashboard (`../frontend/`) and the ships (`../ships/`) are described in `../README.md`.

    uv sync
    uv run pytest
    uv run alembic upgrade head
    uv run thorp dash          # http://localhost:8787
