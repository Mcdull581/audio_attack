"""
Low-level audio read/write utilities using soundfile (torchaudio-compatible).

All paths are resolved via pathlib.  Multi-channel audio is converted
to mono by averaging channels on load.  Audio is resampled to 16 kHz
by default for Wav2Vec2 compatibility.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import soundfile as sf
import torch
import torchaudio.functional as F

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE: int = 16000


def load_wav(path: str | Path, target_sr: int = TARGET_SAMPLE_RATE) -> Tuple[torch.Tensor, int]:
    """Load an audio file and return ``(waveform, sample_rate)``.

    Supports MP3, WAV, FLAC, OGG via soundfile backend.
    The returned waveform is **mono** (shape ``(samples,)``) and resampled
    to *target_sr* Hz.
    Stereo or multi-channel files are averaged to a single channel.
    """
    path = Path(path)
    data, orig_sr = sf.read(str(path), dtype="float32")

    # Convert numpy → torch
    waveform = torch.from_numpy(data).float()

    # Handle multi-channel → mono
    if waveform.dim() > 1 and waveform.shape[-1] > 1:
        waveform = waveform.mean(dim=-1)

    # Resample to target rate
    if orig_sr != target_sr:
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)
        waveform = F.resample(waveform, orig_freq=orig_sr, new_freq=target_sr)
        if waveform.shape[0] == 1:
            waveform = waveform.squeeze(0)

    # Normalize to [-1, 1]
    max_val = waveform.abs().max()
    if max_val > 1.0:
        waveform = waveform / max_val

    return waveform, target_sr


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
        Audio samples in ``[-1.0, 1.0]``.  Shape ``(samples,)`` for mono.
    sample_rate:
        Sample rate in Hz (e.g. 16000).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to numpy in [-1.0, 1.0]
    data = waveform.detach().cpu().numpy()
    if data.ndim > 1:
        data = data.squeeze()

    data = np.clip(data, -1.0, 1.0).astype(np.float32)

    sf.write(str(path), data, sample_rate, subtype="PCM_16")


def get_audio_info(path: str | Path) -> dict:
    """Return metadata for an audio file without loading samples.

    Returns a dict with keys ``duration``, ``sample_rate``, ``num_frames``.
    """
    path = Path(path)
    info = sf.info(str(path))
    return {
        "duration": info.duration,
        "sample_rate": info.samplerate,
        "num_frames": info.frames,
    }
