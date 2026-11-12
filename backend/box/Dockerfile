# The box image (12 November, Justin: "lets do a pre built image"): what a hired GPU sails with, built once, so a
# hire stops downloading torch. Until then every hire ran `uv sync --group torch` and fetched about 6 GB of CUDA
# 13.2 wheels; on a slow host that was 9 minutes of a GPU billed and idle.
#
# The base is the image the charter has always hired with (its ssh works on Vast.ai, and hosts often hold its
# layers already). On top: rsync, uv where the charter looks for it, and the torch group's venv at the path the box
# uses, /root/thorp/backend/.venv, synced from the lock without the project. On the box the charter's own
# `uv sync` then has nothing to fetch: it installs Thorp itself, editable, in seconds.
#
# Built by .github/workflows/box-image.yml whenever backend/uv.lock changes, tagged with the lock's hash, so the
# charter can ask for the image that matches the lock it is sailing with (s1_operations/charter.box_image).
# Holds third-party packages only: no Thorp code, no data, no key.
FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends rsync curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}" UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1

WORKDIR /root/thorp
COPY backend/pyproject.toml backend/uv.lock backend/
RUN uv sync --project backend --group torch --group tagger --frozen --no-install-project \
    && backend/.venv/bin/python -c "import spacy; spacy.load('en_core_web_sm'); print('tagger', spacy.__version__)" \
    && rm -rf /root/.cache/uv \
    && backend/.venv/bin/python -c "import torch; print('torch', torch.__version__, 'cuda', torch.version.cuda)"
