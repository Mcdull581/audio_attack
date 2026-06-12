"""
REST endpoints for sample listing, attack configuration, and audio download.

All routes are mounted under ``/api`` (prefix applied in main.py).
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import (
    AttackConfigIn,
    AttackResponse,
    AttackStatus,
    AttackJob,
    SampleInfo,
    SampleListResponse,
    DATA_DIR,
)
from ..engine.loader import preload_dataset
from .ws import attack_jobs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# ── Helpers ─────────────────────────────────────────────────────────────────

def _read_manifest() -> tuple[List[dict], Path | None]:
    """Return (samples_list, manifest_path_or_None)."""
    manifest_path = Path(__file__).resolve().parent.parent.parent / "data" / "samples_manifest.json"
    if not manifest_path.exists():
        logger.warning("Sample manifest not found at %s", manifest_path)
        return ([], None)
    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return (data, manifest_path)
    if isinstance(data, dict):
        return (data.get("samples", data.get("data", [])), manifest_path)
    return ([], manifest_path)


# ── Sample endpoints ────────────────────────────────────────────────────────

@router.get("/samples", response_model=SampleListResponse)
async def list_samples() -> SampleListResponse:
    """Return all cached audio samples from the manifest."""
    raw_samples, _ = _read_manifest()
    samples: List[SampleInfo] = []
    for entry in raw_samples:
        try:
            samples.append(SampleInfo(
                name=entry["name"],
                local_path=entry.get("local_path", ""),
                duration_sec=float(entry.get("duration_sec", 0)),
                transcription=entry.get("transcription", ""),
            ))
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Skipping malformed manifest entry: %s — %s", entry, exc)
    return SampleListResponse(samples=samples, total=len(samples))


@router.post("/samples/preload")
async def preload_samples() -> dict:
    """Trigger the dataset download / caching pipeline."""
    logger.info("Preload requested via REST")
    try:
        preload_dataset()
        return {"status": "preloading", "message": "Dataset preload initiated."}
    except Exception as exc:
        logger.exception("Preload failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Attack endpoints ────────────────────────────────────────────────────────

@router.post("/attack/start", response_model=AttackResponse)
async def start_attack(config: AttackConfigIn) -> AttackResponse:
    """Create an AttackJob and return its ID. The actual attack starts
    when the client connects via WebSocket to ``/ws/attack/{attack_id}``."""
    raw_samples, manifest_path = _read_manifest()

    # Validate the requested sample exists
    matched = [s for s in raw_samples if s.get("name") == config.sample_name]
    if not matched:
        raise HTTPException(
            status_code=404,
            detail=f"Sample {config.sample_name!r} not found in manifest. "
                   f"Available: {[s.get('name') for s in raw_samples]}",
        )

    sample = matched[0]
    attack_id = str(uuid.uuid4())

    job = AttackJob(
        attack_id=attack_id,
        config=config,
        status=AttackStatus.QUEUED,
        original_transcription=sample.get("transcription", ""),
        waveform_path=sample.get("local_path", ""),
    )

    attack_jobs[attack_id] = job
    logger.info("AttackJob created: id=%s sample=%s target=%r", attack_id, config.sample_name, config.target_phrase)

    return AttackResponse(attack_id=attack_id, status=AttackStatus.QUEUED, config=config)


@router.get("/attack/{attack_id}/status")
async def attack_status(attack_id: str) -> dict:
    """Return the current status of an AttackJob."""
    job = attack_jobs.get(attack_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No attack found for id={attack_id!r}")
    return {
        "attack_id": job.attack_id,
        "status": job.status.value,
        "config": job.config.model_dump(),
        "original_transcription": job.original_transcription,
    }


# ── Audio download ──────────────────────────────────────────────────────────

_VALID_AUDIO_TYPES = {"original", "adversarial", "delta"}


@router.get("/audio/download/{type}/{filename}")
async def download_audio(type: str, filename: str) -> FileResponse:
    """Serve a WAV file from the sampled audio directory.

    *type* must be one of ``original``, ``adversarial``, ``delta``.
    The file is looked up under ``DATA_DIR / type / filename``.
    """
    if type not in _VALID_AUDIO_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid audio type {type!r}. Must be one of {sorted(_VALID_AUDIO_TYPES)}")

    # Basic path traversal guard
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = DATA_DIR / type / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {type}/{filename}")

    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=filename,
    )
