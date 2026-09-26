# Audio Adversarial Attack Lab - Backend Container
# CUDA 12.4 runtime + Python 3.10 for GPU-accelerated PGD attacks on Wav2Vec2
#
# .dockerignore should contain at least:
#   __pycache__/
#   *.pyc
#   .git/
#   data/
#   venv/
#   .venv/
#   *.egg-info/
#   .pytest_cache/
#   .mypy_cache/

FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

LABEL org.opencontainers.image.description="PGD adversarial attack lab backend - GPU-accelerated Wav2Vec2 ASR attack engine"
LABEL org.opencontainers.image.source="audio-attack-lab"

# ── System packages: Python 3.10 + audio codecs ────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python3.10 python3.10-venv python3.10-dev \
    libsndfile1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# ── Python virtual environment ─────────────────────────────────────────────
RUN python3.10 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# ── Dependencies ───────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ───────────────────────────────────────────────────────
COPY app/ ./app/
COPY data/ ./data/

# ── Runtime assets ─────────────────────────────────────────────────────────
RUN mkdir -p /app/data/sampled

# ── Port ───────────────────────────────────────────────────────────────────
EXPOSE 28000

# ── Runtime configuration ──────────────────────────────────────────────────
ENV OMP_NUM_THREADS=1

# ── Entrypoint ─────────────────────────────────────────────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "28000", "--log-level", "info"]
