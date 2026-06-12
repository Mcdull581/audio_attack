"""
Streaming downloader for Mozilla Common Voice (English).

Downloads 100 short speech samples, preprocesses them, and caches the
results as 16-bit PCM .wav files.  A ``samples_manifest.json`` file records
metadata for every cached sample.  Subsequent calls are idempotent — if the
manifest already exists the download is skipped entirely.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import torch
import torchaudio
from datasets import load_dataset

from ..config import (
    DATA_DIR,
    MAX_DURATION_SEC,
    MIN_DURATION_SEC,
    NUM_SAMPLES,
    SAMPLE_RATE,
)
from .preprocess import normalize_audio, resample_if_needed, trim_to_duration

logger = logging.getLogger(__name__)

MANIFEST_PATH: Path = DATA_DIR.parent / "samples_manifest.json"


def _duration_in_range(example: Dict[str, Any]) -> bool:
    """Return ``True`` when the raw audio duration is within the target band."""
    audio = example["audio"]
    duration = len(audio["array"]) / audio["sampling_rate"]
    return MIN_DURATION_SEC <= duration <= MAX_DURATION_SEC


def prepare_samples() -> List[Dict[str, Any]]:
    """Stream, preprocess, cache, and return sample metadata.

    On the first call the function streams the *Common Voice 25.0* English
    test split, filters clips to ``[MIN_DURATION_SEC, MAX_DURATION_SEC]``,
    takes ``NUM_SAMPLES`` entries, and for each one:

    * resamples to ``SAMPLE_RATE`` Hz
    * trims to a high-energy segment
    * peak-normalises to [-1, 1]
    * saves a 16-bit PCM .wav under ``DATA_DIR``
    * records metadata in ``samples_manifest.json``

    If the manifest file already exists it is loaded and returned immediately
    (idempotent).
    """
    # ── Idempotent cache hit ───────────────────────────────────────────
    if MANIFEST_PATH.exists():
        logger.info("Manifest found at %s — loading cached samples", MANIFEST_PATH)
        with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
            manifest: List[Dict[str, Any]] = json.load(fh)
        logger.info("Loaded %d samples from manifest", len(manifest))
        return manifest

    # ── Stream & filter ────────────────────────────────────────────────
    logger.info(
        "Streaming %s/%s (split=%s) …",
        "mozilla-foundation/common_voice_25_0",
        "en",
        "test",
    )
    ds = load_dataset(
        "mozilla-foundation/common_voice_25_0",
        "en",
        split="test",
        streaming=True,
        trust_remote_code=True,
    )

    ds = ds.filter(_duration_in_range)
    ds = ds.take(NUM_SAMPLES)

    # ── Process every sample ───────────────────────────────────────────
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest: List[Dict[str, Any]] = []

    for idx, row in enumerate(ds, start=1):
        name = f"cv_en_{idx:05d}"
        audio_dict = row["audio"]

        # Extract raw numpy audio + metadata
        audio_array = audio_dict["array"]
        orig_sr: int = audio_dict["sampling_rate"]
        transcription: str = row["sentence"]

        # Convert to torch tensor
        waveform = torch.from_numpy(audio_array).float()

        # Preprocessing pipeline
        waveform = resample_if_needed(waveform, orig_sr, SAMPLE_RATE)
        waveform = trim_to_duration(
            waveform, SAMPLE_RATE, MIN_DURATION_SEC, MAX_DURATION_SEC
        )
        waveform = normalize_audio(waveform)

        # Compute duration from final tensor shape
        num_samples = waveform.shape[0] if waveform.dim() == 1 else waveform.shape[-1]
        duration_sec = num_samples / SAMPLE_RATE

        # torchaudio.save expects (channels, samples)
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)

        wav_filename = f"{name}.wav"
        wav_path = DATA_DIR / wav_filename
        torchaudio.save(
            str(wav_path),
            waveform,
            SAMPLE_RATE,
            encoding="PCM_S",
            bits_per_sample=16,
        )

        entry: Dict[str, Any] = {
            "name": name,
            "local_path": f"sampled/{wav_filename}",
            "duration_sec": round(duration_sec, 2),
            "transcription": transcription,
        }
        manifest.append(entry)

        logger.info(
            "[%03d/%d]  %s  (%.2f s)  %s",
            idx,
            NUM_SAMPLES,
            name,
            duration_sec,
            transcription[:80],
        )

    # ── Write manifest ─────────────────────────────────────────────────
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    logger.info(
        "Wrote manifest with %d entries to %s", len(manifest), MANIFEST_PATH
    )
    return manifest


# Alias for callers that expect the name "preload_dataset"
preload_dataset = prepare_samples
