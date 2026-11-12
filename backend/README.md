# Nothing up my sleeve: the backend

The Python package (`thorp/`), its tests, scripts and the Alembic migrations of the Postgres fitout store.
The project, the dashboard (`../frontend/`) and the ships (`../ships/`) are described in `../README.md`.

    uv sync
    uv run pytest
    uv run alembic upgrade head
    uv run thorp dash          # http://localhost:8787

On an NVIDIA GPU a voyage trains on PyTorch instead of MLX (`model.backend: torch` or `THORP_BACKEND=torch`):
`uv sync --group torch`, then see `CUDA.md`.
