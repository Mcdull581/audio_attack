"""
Low-level wav read/write utilities using torchaudio.

All paths are resolved via pathlib.  Multi-channel audio is converted
to mono by averaging channels on load.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import torch
import torchaudio

logger = logging.getLogger(__name__)


def load_wav(path: str | Path) -> Tuple[torch.Tensor, int]:
    """Load a .wav file and return ``(waveform, sample_rate)``.

    The returned waveform is **mono** (shape ``(samples,)``).  Stereo or
    multi-channel files are averaged to a single channel.
    """
    path = Path(path)
    waveform, sample_rate = torchaudio.load(str(path))

    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    return waveform.squeeze(0), sample_rate


def save_wav(
    path: str | Path,
    waveform: torch.Tensor,
    sample_rate: int,
) -> None:
    """Save *waveform* as a 16-bit signed PCM .wav file.

    Parameters
    ----------
    path:
        Destination path (parent directories are created if needed).
    waveform:
        Audio samples in ``[-1.0, 1.0]``.  Shape ``(samples,)`` for mono
        or ``(channels, samples)`` for multi-channel.
    sample_rate:
        Sample rate in Hz (e.g. 16000).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # torchaudio.save expects (channels, samples)
    if waveform.dim() == 1:
        waveform = waveform.unsqueeze(0)

    waveform = waveform.clamp(-1.0, 1.0)

    torchaudio.save(
        str(path),
        waveform,
        sample_rate,
        encoding="PCM_S",
        bits_per_sample=16,
    )


def get_audio_info(path: str | Path) -> dict:
    """Return metadata for a .wav file without loading samples.

    Returns a dict with keys ``duration``, ``sample_rate``, ``num_frames``.
    """
    path = Path(path)
    info = torchaudio.info(str(path))
    return {
        "duration": info.num_frames / info.sample_rate,
        "sample_rate": info.sample_rate,
        "num_frames": info.num_frames,
    }
