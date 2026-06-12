"""
FastAPI application entry point for the Audio Adversarial Attack Lab.

Starts the uvicorn server, wires CORS, routers, static file serving,
and a lifespan context manager that preloads the Wav2Vec2 model and
seeds sample data on start-up.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.rest import router as rest_router
from .api.ws import router as ws_router, attack_jobs
from .config import DATA_DIR, MODEL_NAME, DEVICE
from .engine.model import Wav2Vec2Wrapper
from .engine.loader import preload_dataset

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("audio_attack")


# ── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application start-up / shut-down logic."""
    # ── Startup ────────────────────────────────────────────────────────
    logger.info("Loading Wav2Vec2 model: %s on %s", MODEL_NAME, DEVICE)
    wrapper = Wav2Vec2Wrapper(model_name=MODEL_NAME, device=DEVICE)
    app.state.wav2vec2_wrapper = wrapper
    logger.info("Wav2Vec2 model ready.")

    # Share the same attack_jobs dict with the REST and WS layers
    app.state.attack_jobs = attack_jobs
    logger.info("Attack job store initialised (shared with ws/rest).")

    # Ensure sampled data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Preload / cache dataset samples
    try:
        logger.info("Triggering sample preload…")
        preload_dataset()
        logger.info("Sample preload complete.")
    except Exception:
        logger.exception("Sample preload failed — continuing anyway")

    yield  # ── application runs here ──

    # ── Shutdown ────────────────────────────────────────────────────────
    logger.info("Shutting down. Cleaning up resources.")
    # Future: close any persistent connections, release GPU memory, etc.


# ── Application ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Audio Adversarial Attack Lab",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(rest_router)   # prefix="/api" is already on the router
app.include_router(ws_router)     # no prefix — endpoints are at /ws/…

# ── Static files ────────────────────────────────────────────────────────────
app.mount(
    "/data",
    StaticFiles(directory=str(DATA_DIR)),
    name="data",
)
