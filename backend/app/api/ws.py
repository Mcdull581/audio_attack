"""
WebSocket endpoint that orchestrates the full CW attack lifecycle.

The handler accepts a connection, spawns the PyTorch attack in a
background thread via ``asyncio.to_thread``, and bridges thread-safe
``queue.Queue`` progress messages back to the WebSocket without
blocking the async event loop.

Architecture
------------
::

    Client ──WebSocket──► ws.py handler
                              │
                   ┌──────────┼──────────┐
                   │                     │
            asyncio event loop     stdlib thread
                   │                     │
            loop.run_in_executor    run_cw_attack_sync()
            (polls queue.Queue)     (pushes progress dicts)
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue  # stdlib — thread-safe, NOT asyncio.Queue
import threading
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import AttackJob, AttackStatus, DATA_DIR
from ..engine.model import Wav2Vec2Wrapper
from ..engine.attack import run_cw_attack_sync
from ..utils.audio_io import load_wav, save_wav
from .websocket_manager import ConnectionManager

logger = logging.getLogger(__name__)

# ── Router ──────────────────────────────────────────────────────────────────
router = APIRouter()

# ── Shared state ────────────────────────────────────────────────────────────
# Populated by main.py at startup and shared with rest.py so that
# REST and WebSocket layers reference the same in-memory job store.
attack_jobs: Dict[str, AttackJob] = {}

# Single connection manager instance for the whole process.
_manager = ConnectionManager()

# ── Helpers ─────────────────────────────────────────────────────────────────

def _load_sample_manifest() -> list[dict]:
    """Load the sample manifest and return its entries as a list of dicts."""
    manifest_path = Path(__file__).resolve().parent.parent.parent / "data" / "samples_manifest.json"
    if not manifest_path.exists():
        logger.warning("Sample manifest not found at %s", manifest_path)
        return []
    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    # The manifest may be a list directly or wrapped in an object.
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("samples", data.get("data", []))
    return []


def _find_sample_duration(sample_name: str) -> float:
    """Return the duration_sec for *sample_name* from the manifest, or 0.0."""
    for entry in _load_sample_manifest():
        if entry.get("name") == sample_name:
            return float(entry.get("duration_sec", 0.0))
    return 0.0

# ── WebSocket endpoint ──────────────────────────────────────────────────────

@router.websocket("/ws/attack/{attack_id}")
async def attack_ws_endpoint(websocket: WebSocket, attack_id: str) -> None:
    """Orchestrate the full CW attack lifecycle over a WebSocket.

    1. Accept & register the connection.
    2. Validate the pre-created AttackJob.
    3. Send ``attack_started`` metadata.
    4. Spawn the PyTorch attack in a thread; bridge progress via
       ``queue.Queue`` → ``run_in_executor`` → WebSocket.
    5. On completion / error, close the connection.
    """
    await _manager.connect(attack_id, websocket)

    # ── Resolve the AttackJob ──────────────────────────────────────────
    job: AttackJob | None = attack_jobs.get(attack_id)
    if job is None:
        await _manager.send_progress(attack_id, {
            "type": "attack_error",
            "attack_id": attack_id,
            "error_code": "UNKNOWN_ATTACK_ID",
            "message": f"No AttackJob found for attack_id={attack_id!r}",
            "timestamp": time.time(),
        })
        await _manager.disconnect(attack_id)
        return

    job.status = AttackStatus.RUNNING

    # ── Resolve the model wrapper from app state ───────────────────────
    wrapper: Wav2Vec2Wrapper = websocket.app.state.wav2vec2_wrapper

    # ── Send attack_started ────────────────────────────────────────────
    push_interval = job.push_interval()
    audio_duration = _find_sample_duration(job.config.sample_name)
    await _manager.send_progress(attack_id, {
        "type": "attack_started",
        "attack_id": attack_id,
        "config": job.config.model_dump(),
        "original_transcription": job.original_transcription,
        "audio_duration_sec": audio_duration,
        "push_interval": push_interval,
    })

    # ── Thread-safe progress queue ─────────────────────────────────────
    q: queue.Queue[dict] = queue.Queue()
    # Cancellation flag — set when WebSocket disconnects to stop the attack thread
    cancel_event = threading.Event()

    def _attack_runner_sync() -> None:
        """Runs in a background thread — PyTorch + file I/O."""
        try:
            # Load source waveform
            wav_path = DATA_DIR.parent / job.waveform_path
            waveform, sr = load_wav(str(wav_path))

            # Build the config dict expected by the engine
            engine_config: Dict[str, Any] = {
                "epsilon": job.config.epsilon,
                "max_iterations": job.config.max_iterations,
                "lambda_l2": job.config.lambda_l2,
                "learning_rate": job.config.learning_rate,
                "cancel_event": cancel_event,  # thread-safe stop signal
            }

            # Progress callback — pushes into the thread-safe queue
            def _progress_cb(msg: dict) -> None:
                q.put(msg)

            # ── Run the attack ─────────────────────────────────────────
            adv, delta, results = run_cw_attack_sync(
                waveform=waveform,
                sample_rate=sr,
                target_phrase=job.config.target_phrase,
                wrapper=wrapper,
                config_dict=engine_config,
                progress_callback=_progress_cb,
            )

            # ── Persist output wavs ────────────────────────────────────
            adv_dir = DATA_DIR / "adversarial"
            delta_dir = DATA_DIR / "delta"
            original_dir = DATA_DIR / "original"
            adv_dir.mkdir(parents=True, exist_ok=True)
            delta_dir.mkdir(parents=True, exist_ok=True)
            original_dir.mkdir(parents=True, exist_ok=True)

            adv_path = adv_dir / f"{attack_id}.wav"
            delta_path = delta_dir / f"{attack_id}.wav"
            original_path = original_dir / f"{attack_id}.wav"

            save_wav(str(adv_path), adv, sr)
            save_wav(str(delta_path), delta, sr)
            save_wav(str(original_path), waveform, sr)

            job.adversarial_path = str(adv_path)
            job.delta_path = str(delta_path)

            # ── Completion message ─────────────────────────────────────
            final_transcription = results.get("final_transcription", job.config.target_phrase)
            success = final_transcription.strip().lower() == job.config.target_phrase.strip().lower()
            q.put({
                "type": "attack_complete",
                "attack_id": attack_id,
                "total_iterations": results.get("total_iterations", job.config.max_iterations),
                "final_ctc_loss": results.get("final_ctc_loss", 0.0),
                "final_l2_norm": results.get("final_l2_norm", 0.0),
                "final_transcription": final_transcription,
                "target_transcription": job.config.target_phrase,
                "success": success,
                "resources": job.result_urls(),
            })

        except Exception:
            logger.exception("Attack thread failed for attack_id=%s", attack_id)
            q.put({
                "type": "attack_error",
                "attack_id": attack_id,
                "error_code": "ATTACK_EXECUTION_FAILED",
                "message": "Unexpected error during attack execution. Check server logs.",
                "timestamp": time.time(),
            })
        finally:
            # ── Explicit GPU / CPU memory cleanup ────────────────────────
            import gc
            import torch
            # Trigger Python GC to release any lingering tensor references
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            logger.debug("Memory cleanup completed for attack_id=%s", attack_id)

    # ── Spawn attack in background thread ──────────────────────────────
    loop = asyncio.get_running_loop()
    _ = asyncio.create_task(asyncio.to_thread(_attack_runner_sync))

    # ── Poll the thread-safe queue ─────────────────────────────────────
    try:
        while True:
            # ``run_in_executor`` uses the default thread-pool executor,
            # which means ``queue.get()`` blocks a thread-pool thread
            # instead of the event loop.
            msg: dict = await loop.run_in_executor(None, q.get)
            msg_type = msg.get("type", "")

            await _manager.send_progress(attack_id, msg)

            if msg_type in ("attack_complete", "attack_error"):
                if msg_type == "attack_complete":
                    job.status = AttackStatus.COMPLETED
                else:
                    job.status = AttackStatus.FAILED
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected mid-attack for attack_id=%s — signalling cancel", attack_id)
        cancel_event.set()  # stop the attack thread
        job.status = AttackStatus.CANCELLED
    except Exception:
        logger.exception("Unexpected error in WebSocket loop for attack_id=%s", attack_id)
        job.status = AttackStatus.FAILED
        await _manager.send_progress(attack_id, {
            "type": "attack_error",
            "attack_id": attack_id,
            "error_code": "WS_LOOP_ERROR",
            "message": "Internal error in progress loop. See server logs.",
            "timestamp": time.time(),
        })
    finally:
        await _manager.disconnect(attack_id)
