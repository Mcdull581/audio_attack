"""
Carlini & Wagner (2018) targeted adversarial attack loop for Wav2Vec2 CTC ASR.

This module provides a **synchronous** entry-point that is wrapped in
``asyncio.to_thread`` by the API layer.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

import torch
import torch.nn.functional as F

from .model import Wav2Vec2Wrapper
from .optimizer import clamp_delta, compute_snr_db, create_adversarial_optimizer

logger = logging.getLogger(__name__)

# ── helpers ────────────────────────────────────────────────────────────────


def _get_feature_length(model: torch.nn.Module, input_length: int) -> int:
    """Return the CTC-compatible time length after the feature extractor."""
    try:
        return int(model._get_feat_extract_output_lengths(input_length))
    except (AttributeError, TypeError):
        return input_length // 320


# ── main attack loop ───────────────────────────────────────────────────────


def run_cw_attack_sync(
    waveform: torch.Tensor,
    sample_rate: int,
    target_phrase: str,
    wrapper: Wav2Vec2Wrapper,
    config_dict: dict,
    progress_callback: Callable[[dict], Any],
) -> tuple:
    """Run the CW-style adversarial attack synchronously.

    Parameters
    ----------
    waveform : torch.Tensor
        Raw audio tensor (1-D or ``(1, T)``).
    sample_rate : int
        Audio sample rate (typically 16 000).
    target_phrase : str
        The target transcription we want the model to output.
    wrapper : Wav2Vec2Wrapper
        Frozen Wav2Vec2 wrapper.
    config_dict : dict
        Must contain keys ``epsilon``, ``max_iterations``, ``lambda_l2``,
        ``learning_rate``.  May optionally contain ``attack_id``.
    progress_callback : Callable
        Called every ``push_interval`` iterations with a progress dict.

    Returns
    -------
    tuple :
        ``(adversarial_waveform, delta_detached, results_dict)``
    """
    # ── unpack config ──────────────────────────────────────────────────
    attack_id: str = config_dict.get("attack_id", "unknown")
    epsilon: float = float(config_dict["epsilon"])
    max_iterations: int = int(config_dict["max_iterations"])
    lambda_l2: float = float(config_dict["lambda_l2"])
    learning_rate: float = float(config_dict["learning_rate"])
    push_interval: int = max(1, max_iterations // 200)

    device = wrapper.device

    # ── normalise waveform shape ───────────────────────────────────────
    if waveform.dim() == 1:
        waveform = waveform.unsqueeze(0)  # → (1, T)

    waveform = waveform.to(device)

    # ── encode target text ─────────────────────────────────────────────
    target_ids = wrapper.encode_text(target_phrase)  # (1, S_target)
    target_len = target_ids.shape[1]

    # ── pre-compute original features ──────────────────────────────────
    encoded = wrapper.encode(waveform, sample_rate=sample_rate)
    input_values_orig = encoded["input_values"]       # (1, T_feat)
    attention_mask = encoded.get("attention_mask")     # may be None

    # ── initialise perturbation ────────────────────────────────────────
    delta = torch.zeros_like(waveform, requires_grad=True)
    optimizer = create_adversarial_optimizer(delta, lr=learning_rate)

    # ── CTC input length (time steps after feature extractor) ──────────
    feat_len = _get_feature_length(wrapper.model, input_values_orig.shape[1])
    input_lengths = torch.full(
        (1,), feat_len, dtype=torch.long, device=device
    )
    target_lengths = torch.tensor([target_len], dtype=torch.long, device=device)

    adv_logits: torch.Tensor | None = None

    logger.info(
        "CW attack start  id=%s  target=%r  ε=%.4f  max_iter=%d  λ=%.2e  lr=%.2e",
        attack_id, target_phrase, epsilon, max_iterations, lambda_l2, learning_rate,
    )

    # ── Main CW loop ──────────────────────────────────────────────────
    for iteration in range(1, max_iterations + 1):
        # a. perturbed input
        adv_input = input_values_orig + delta

        # b. forward  (grads flow to delta, model params are frozen)
        adv_logits = wrapper.get_logits(adv_input, attention_mask=attention_mask)
        # adv_logits: (1, T_steps, V)

        # c. CTC loss
        log_probs = F.log_softmax(adv_logits, dim=-1)          # (1, T, V)
        log_probs_ctc = log_probs.transpose(0, 1)              # (T, 1, V)

        ctc_loss = F.ctc_loss(
            log_probs_ctc,
            target_ids.squeeze(0),      # (S_target,)
            input_lengths,              # (1,)
            target_lengths,             # (1,)
            blank=0,
            reduction="mean",
            zero_infinity=True,
        )

        # d. L₂ regularisation
        l2_norm = delta.norm(p=2)

        # e. total loss
        total_loss = ctc_loss + lambda_l2 * l2_norm

        # f. backward + step
        optimizer.zero_grad()
        total_loss.backward()
        optimizer.step()

        # g. project delta into ℓ∞ ball
        clamp_delta(delta, epsilon)

        # h. progress reporting
        if iteration % push_interval == 0 or iteration == max_iterations:
            with torch.no_grad():
                current_text = wrapper.decode(adv_logits)
                snr = compute_snr_db(waveform, delta)

            progress_callback({
                "type": "iteration_progress",
                "attack_id": attack_id,
                "iteration": iteration,
                "ctc_loss": float(ctc_loss.item()),
                "l2_loss": float(l2_norm.item()),
                "total_loss": float(total_loss.item()),
                "l2_norm_delta": float(l2_norm.item()),
                "snr_db": snr,
                "current_transcription": current_text,
                "target_transcription": target_phrase,
                "timestamp": time.time(),
            })

    # ── final results ─────────────────────────────────────────────────
    with torch.no_grad():
        final_text = wrapper.decode(adv_logits)
        final_ctc = float(ctc_loss.item()) if adv_logits is not None else float("nan")
        final_l2 = float(l2_norm.item())

    success = (final_text.lower().strip() == target_phrase.lower().strip())

    adversarial_waveform = (input_values_orig + delta).detach()

    results_dict: dict = {
        "success": success,
        "final_transcription": final_text,
        "total_iterations": max_iterations,
        "final_ctc_loss": final_ctc,
        "final_l2_norm": final_l2,
    }

    logger.info(
        "CW attack finished  id=%s  success=%s  final_text=%r  ctc=%.4f  l2=%.4f",
        attack_id, success, final_text, final_ctc, final_l2,
    )

    return adversarial_waveform, delta.detach(), results_dict
