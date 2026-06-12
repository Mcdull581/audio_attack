"""
Adversarial-perturbation optimizer helpers for the CW attack engine.
"""

from __future__ import annotations

import logging

import torch

logger = logging.getLogger(__name__)


def create_adversarial_optimizer(
    delta: torch.Tensor, lr: float
) -> torch.optim.Adam:
    """Return an Adam optimizer that only updates *delta*."""
    logger.debug("Creating Adam optimizer for delta  lr=%.2e", lr)
    return torch.optim.Adam([delta], lr=lr)


def clamp_delta(delta: torch.Tensor, epsilon: float) -> None:
    """In-place element-wise clamp to [-epsilon, epsilon]."""
    delta.data.clamp_(-epsilon, epsilon)


def project_delta_l2(delta: torch.Tensor, max_norm: float) -> None:
    """Optional in-place L₂ projection: if norm exceeds *max_norm*, scale to fit."""
    if max_norm <= 0:
        return
    current_norm = delta.data.norm(p=2)
    if current_norm > max_norm:
        scale = max_norm / (current_norm + 1e-12)
        delta.data.mul_(scale)


def compute_snr_db(original: torch.Tensor, perturbation: torch.Tensor) -> float:
    """Compute Signal-to-Noise Ratio in dB.

    SNR = 20 * log10(RMS_signal / RMS_noise)
    """
    EPS = 1e-10
    signal_rms = original.detach().norm(p=2) / max(original.numel() ** 0.5, 1.0)
    noise_rms = perturbation.detach().norm(p=2) / max(perturbation.numel() ** 0.5, 1.0)
    # Protect against log(0) or log(negative).
    noise_rms = max(noise_rms, EPS)
    snr_db = float(20.0 * torch.log10(signal_rms / noise_rms))
    return snr_db
