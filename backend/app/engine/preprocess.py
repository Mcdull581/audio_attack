"""
Audio preprocessing routines: resample, energy-based trimming, normalisation.

All functions accept and return **mono** ``torch.Tensor`` values.  Multi-channel
input is averaged to mono before processing.
"""

from __future__ import annotations

import logging

import torch
import torchaudio.functional as AF

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────


def _to_mono(waveform: torch.Tensor) -> torch.Tensor:
    """Average channels to mono; keep shape ``(1, samples)``."""
    if waveform.dim() == 1:
        return waveform.unsqueeze(0)
    if waveform.shape[0] > 1:
        return waveform.mean(dim=0, keepdim=True)
    return waveform


# ── public API ─────────────────────────────────────────────────────────────


def resample_if_needed(
    waveform: torch.Tensor,
    orig_sr: int,
    target_sr: int = 16000,
) -> torch.Tensor:
    """Resample *waveform* to *target_sr* when the rates differ.

    Returns a **1-D mono** tensor ``(samples,)``.
    """
    waveform = _to_mono(waveform)  # (1, samples)

    if orig_sr == target_sr:
        return waveform.squeeze(0)

    resampled = AF.resample(waveform, orig_freq=orig_sr, new_freq=target_sr)
    return resampled.squeeze(0)  # (samples,)


def trim_to_duration(
    waveform: torch.Tensor,
    sr: int,
    min_sec: float,
    max_sec: float,
) -> torch.Tensor:
    """Extract a high-energy segment whose length falls inside
    *[min_sec, max_sec]*.

    The algorithm slides a window of ``target_duration = (min_sec + max_sec) / 2``
    across the waveform and picks the position with the highest RMS energy.

    Returns a **1-D mono** tensor ``(samples,)``.  If the input is shorter
    than *target_duration* it is returned unchanged.
    """
    waveform = _to_mono(waveform)  # (1, samples)
    total_samples = waveform.shape[-1]
    total_duration = total_samples / sr

    # Already in range → nothing to do
    if min_sec <= total_duration <= max_sec:
        return waveform.squeeze(0)

    target_duration = (min_sec + max_sec) / 2.0
    target_samples = int(target_duration * sr)

    if total_samples <= target_samples:
        return waveform.squeeze(0)

    # Slide a window with 100 ms hop and pick the loudest segment
    hop = max(1, sr // 10)
    best_start = 0
    best_rms = 0.0

    for start in range(0, total_samples - target_samples + 1, hop):
        window = waveform[..., start : start + target_samples]
        rms = torch.sqrt(torch.mean(window**2)).item()
        if rms > best_rms:
            best_rms = rms
            best_start = start

    trimmed = waveform[
        ..., best_start : best_start + target_samples
    ]
    return trimmed.squeeze(0)


def normalize_audio(waveform: torch.Tensor) -> torch.Tensor:
    """Peak-normalise *waveform* so that ``max(|samples|) == 1.0``.

    Silent input is returned unchanged.
    """
    max_val = waveform.abs().max()
    if max_val > 0:
        waveform = waveform / max_val
    return waveform
