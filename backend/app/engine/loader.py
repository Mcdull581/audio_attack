"""
Local audio file scanner — replaces HF streaming for offline testing.

Scans ``backend/data/sampled/`` for pre-placed audio files (.mp3 / .wav),
reads their metadata via torchaudio, and generates ``samples_manifest.json``.
No network required — works entirely with local files.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import soundfile as sf

from ..config import DATA_DIR, MAX_DURATION_SEC, MIN_DURATION_SEC

logger = logging.getLogger(__name__)

MANIFEST_PATH: Path = DATA_DIR.parent / "samples_manifest.json"

# Supported audio extensions (case-insensitive)
_AUDIO_GLOBS = ("*.mp3", "*.wav", "*.flac", "*.ogg", "*.m4a")


def prepare_samples() -> List[Dict[str, Any]]:
    """Scan local audio files and generate manifest metadata.

    On the first call the function scans ``DATA_DIR`` for audio files,
    reads duration / sample rate via ``torchaudio.info()`` (header-only,
    no full decode), optionally filters by duration, and writes
    ``samples_manifest.json``.

    If the manifest already exists it is loaded and returned immediately
    (idempotent).
    """
    # ── Idempotent cache hit ───────────────────────────────────────────
    if MANIFEST_PATH.exists():
        logger.info("Manifest found at %s — loading cached samples", MANIFEST_PATH)
        with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
            manifest: List[Dict[str, Any]] = json.load(fh)
        logger.info("Loaded %d samples from manifest", len(manifest))
        return manifest

    # ── Scan local directory ───────────────────────────────────────────
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    audio_files: List[Path] = []
    for glob_pattern in _AUDIO_GLOBS:
        audio_files.extend(sorted(DATA_DIR.glob(glob_pattern)))

    if not audio_files:
        logger.warning(
            "No audio files found in %s. Place .mp3/.wav files in this directory.",
            DATA_DIR,
        )
        manifest: List[Dict[str, Any]] = []
        with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
        return manifest

    logger.info("Scanning %d local audio files in %s …", len(audio_files), DATA_DIR)

    # ── Build manifest ────────────────────────────────────────────────
    manifest: List[Dict[str, Any]] = []

    for idx, file_path in enumerate(audio_files, start=1):
        try:
            info = sf.info(str(file_path))
        except Exception:
            logger.warning("Skipping unreadable file: %s", file_path.name)
            continue

        duration_sec = info.duration

        # Optional duration filter — include all if range covers everything
        if not (MIN_DURATION_SEC <= duration_sec <= MAX_DURATION_SEC):
            logger.debug(
                "Skipping %s (%.2fs outside [%.1f, %.1f] range)",
                file_path.name, duration_sec, MIN_DURATION_SEC, MAX_DURATION_SEC,
            )
            continue

        # Derive name from filename (strip extension)
        name = file_path.stem  # e.g. "common_voice_en_1"
        # Build relative path from DATA_DIR
        rel_path = f"sampled/{file_path.name}"

        entry: Dict[str, Any] = {
            "name": name,
            "local_path": rel_path,
            "duration_sec": round(duration_sec, 2),
            "transcription": "",  # no transcription for local files
        }
        manifest.append(entry)

        if idx % 50 == 0:
            logger.info("[%d/%d] scanned …", len(manifest), len(audio_files))

    # ── Write manifest ─────────────────────────────────────────────────
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    logger.info(
        "Wrote manifest with %d entries to %s (%d files skipped)",
        len(manifest), MANIFEST_PATH, len(audio_files) - len(manifest),
    )
    return manifest


# Alias for callers that expect the name "preload_dataset"
preload_dataset = prepare_samples
