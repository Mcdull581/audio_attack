"""
Targeted PGD attack with momentum and multiple restarts for Wav2Vec2 CTC ASR.

The synchronous entry-point is wrapped in ``asyncio.to_thread`` by the API
layer. The attack stays in processor space (the exact tensor consumed by the
frozen model) and restores the original waveform scale for saved files.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Callable

import torch
import torch.nn.functional as F

from .model import Wav2Vec2Wrapper
from .optimizer import clamp_delta, compute_snr_db

logger = logging.getLogger(__name__)


def _get_feature_length(model: torch.nn.Module, input_length: int) -> int:
    """Return the CTC-compatible time length after the feature extractor."""
    try:
        return int(model._get_feat_extract_output_lengths(input_length))
    except (AttributeError, TypeError):
        return input_length // 320


def _restore_waveform_scale(
    processed_waveform: torch.Tensor,
    original_waveform: torch.Tensor,
    wrapper: Wav2Vec2Wrapper,
) -> torch.Tensor:
    """Map processor-space waveform back to the original audio scale."""
    feature_extractor = wrapper.processor.feature_extractor
    if not getattr(feature_extractor, "do_normalize", False):
        return processed_waveform

    mean = original_waveform.mean()
    std = torch.sqrt(original_waveform.var(unbiased=False) + 1e-7)
    return processed_waveform * std + mean


def _normalise_text(text: str) -> str:
    """Use conservative normalisation for success checks and ranking."""
    return re.sub(r"\s+", " ", text.casefold().strip())


def _edit_distance(left: str, right: str) -> int:
    """Return character-level Levenshtein distance for ranking candidates."""
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


def _ctc_loss(
    logits: torch.Tensor,
    target_ids: torch.Tensor,
    input_lengths: torch.Tensor,
    target_lengths: torch.Tensor,
) -> torch.Tensor:
    """Compute targeted CTC loss from batch-first logits."""
    return F.ctc_loss(
        F.log_softmax(logits, dim=-1).transpose(0, 1),
        target_ids.squeeze(0),
        input_lengths,
        target_lengths,
        blank=0,
        reduction="mean",
        zero_infinity=True,
    )


def run_cw_attack_sync(
    waveform: torch.Tensor,
    sample_rate: int,
    target_phrase: str,
    wrapper: Wav2Vec2Wrapper,
    config_dict: dict,
    progress_callback: Callable[[dict], Any],
) -> tuple:
    """Run targeted momentum-PGD with random restarts.

    ``max_iterations`` is the number of projected gradient steps per restart;
    ``restarts`` includes the deterministic zero start. The returned
    iteration count is the number of actual gradient steps across all starts.
    The best candidate is retained by (exact match, edit distance, CTC loss),
    so a late regression cannot replace an earlier better result.
    """
    attack_id: str = config_dict.get("attack_id", "unknown")
    epsilon = float(config_dict["epsilon"])
    max_iterations = int(config_dict["max_iterations"])
    lambda_l2 = float(config_dict["lambda_l2"])
    learning_rate = float(config_dict["learning_rate"])
    momentum = float(config_dict.get("momentum", 0.9))
    restarts = int(config_dict.get("restarts", 3))
    push_interval = max(1, (max_iterations * restarts) // 200)
    cancel_event = config_dict.get("cancel_event")
    total_budget = max_iterations * restarts

    device = wrapper.device
    if str(waveform.device) != str(device):
        waveform = waveform.to(device)
    if waveform.dim() > 1:
        waveform = waveform.squeeze(0)
    waveform = waveform.to(device)

    target_ids = wrapper.encode_text(target_phrase)
    target_len = target_ids.shape[1]
    encoded = wrapper.encode(waveform, sample_rate=sample_rate)
    input_values_orig = encoded["input_values"]
    attention_mask = encoded.get("attention_mask")

    feat_len = _get_feature_length(wrapper.model, input_values_orig.shape[1])
    input_lengths = torch.full((1,), feat_len, dtype=torch.long, device=device)
    target_lengths = torch.tensor([target_len], dtype=torch.long, device=device)
    target_normalised = _normalise_text(target_phrase)

    best_delta: torch.Tensor | None = None
    best_text = ""
    best_ctc = float("inf")
    best_l2 = float("inf")
    best_score: tuple[int, int, float] | None = None
    completed_iterations = 0
    success_found = False
    restarts_completed = 0

    logger.info(
        "PGD attack start id=%s target=%r epsilon=%.4f max_iter=%d "
        "momentum=%.3f restarts=%d lambda=%.2e step=%.2e",
        attack_id,
        target_phrase,
        epsilon,
        max_iterations,
        momentum,
        restarts,
        lambda_l2,
        learning_rate,
    )

    def record_candidate(
        candidate_delta: torch.Tensor,
        candidate_text: str,
        candidate_ctc: float,
    ) -> bool:
        """Retain the best candidate and return whether it exactly matches."""
        nonlocal best_delta, best_text, best_ctc, best_l2, best_score
        normalised = _normalise_text(candidate_text)
        distance = _edit_distance(normalised, target_normalised)
        exact = int(normalised == target_normalised)
        candidate_l2 = float(candidate_delta.norm(p=2).item())
        candidate_score = (0 if exact else 1, distance, candidate_ctc)
        if best_score is None or candidate_score < best_score:
            best_delta = candidate_delta.detach().clone()
            best_text = candidate_text
            best_ctc = candidate_ctc
            best_l2 = candidate_l2
            best_score = candidate_score
        return bool(exact)

    def report_progress(
        *,
        candidate_delta: torch.Tensor,
        candidate_text: str,
        candidate_ctc: float,
        global_iteration: int,
        restart_index: int,
        restart_iteration: int,
        total_loss: float,
    ) -> None:
        candidate_waveform = _restore_waveform_scale(
            (input_values_orig + candidate_delta).squeeze(0), waveform, wrapper
        )
        snr = compute_snr_db(waveform, candidate_waveform - waveform)
        progress_callback({
            "type": "iteration_progress",
            "attack_id": attack_id,
            "iteration": global_iteration,
            "ctc_loss": candidate_ctc,
            "l2_loss": float(candidate_delta.norm(p=2).item()),
            "total_loss": total_loss,
            "l2_norm_delta": float(candidate_delta.norm(p=2).item()),
            "snr_db": snr,
            "current_transcription": candidate_text,
            "target_transcription": target_phrase,
            "restart_index": restart_index,
            "restarts": restarts,
            "restart_iteration": restart_iteration,
            "total_iterations_budget": total_budget,
            "timestamp": time.time(),
        })

    for restart_index_zero in range(restarts):
        if cancel_event is not None and cancel_event.is_set():
            break
        restarts_completed = restart_index_zero + 1

        if restart_index_zero == 0:
            delta = torch.zeros_like(input_values_orig)
        else:
            # Random starts explore different points in the L-infinity ball.
            delta = torch.empty_like(input_values_orig).uniform_(-epsilon, epsilon)
        delta = delta.detach().requires_grad_(True)
        momentum_buffer = torch.zeros_like(delta)

        for restart_iteration in range(1, max_iterations + 1):
            if cancel_event is not None and cancel_event.is_set():
                break

            adv_input = input_values_orig + delta
            adv_logits = wrapper.get_logits(adv_input, attention_mask=attention_mask)
            with torch.no_grad():
                current_text = wrapper.decode(adv_logits.detach())
            ctc_loss = _ctc_loss(
                adv_logits, target_ids, input_lengths, target_lengths
            )
            l2_norm = delta.norm(p=2)
            total_loss = ctc_loss + lambda_l2 * l2_norm
            current_ctc = float(ctc_loss.detach().item())

            # Check before updating so success cannot be lost by a later step.
            if record_candidate(delta, current_text, current_ctc):
                success_found = True
                report_progress(
                    candidate_delta=delta,
                    candidate_text=current_text,
                    candidate_ctc=current_ctc,
                    global_iteration=completed_iterations,
                    restart_index=restart_index_zero + 1,
                    restart_iteration=restart_iteration - 1,
                    total_loss=float(total_loss.detach().item()),
                )
                break

            gradient = torch.autograd.grad(
                total_loss, delta, retain_graph=False, create_graph=False
            )[0]
            gradient = torch.nan_to_num(gradient)
            gradient_scale = gradient.abs().mean().clamp_min(1e-12)
            normalised_gradient = gradient / gradient_scale
            momentum_buffer = momentum * momentum_buffer + normalised_gradient

            # Targeted PGD minimises the target CTC objective.
            with torch.no_grad():
                delta.sub_(learning_rate * momentum_buffer.sign())
                clamp_delta(delta, epsilon)
            delta = delta.detach().requires_grad_(True)
            completed_iterations += 1

            should_report = (
                completed_iterations % push_interval == 0
                or completed_iterations == total_budget
            )
            if should_report:
                with torch.no_grad():
                    candidate_input = input_values_orig + delta
                    candidate_logits = wrapper.get_logits(
                        candidate_input, attention_mask=attention_mask
                    )
                    candidate_text = wrapper.decode(candidate_logits)
                    candidate_ctc = float(_ctc_loss(
                        candidate_logits,
                        target_ids,
                        input_lengths,
                        target_lengths,
                    ).item())
                candidate_total = candidate_ctc + lambda_l2 * float(delta.norm(p=2).item())
                candidate_success = record_candidate(delta, candidate_text, candidate_ctc)
                report_progress(
                    candidate_delta=delta,
                    candidate_text=candidate_text,
                    candidate_ctc=candidate_ctc,
                    global_iteration=completed_iterations,
                    restart_index=restart_index_zero + 1,
                    restart_iteration=restart_iteration,
                    total_loss=candidate_total,
                )

                if candidate_success:
                    success_found = True
                    break

        if success_found or (cancel_event is not None and cancel_event.is_set()):
            break

    if best_delta is None:
        best_delta = torch.zeros_like(input_values_orig)

    with torch.no_grad():
        final_adv_input = input_values_orig + best_delta
        final_logits = wrapper.get_logits(
            final_adv_input, attention_mask=attention_mask
        )
        final_text = wrapper.decode(final_logits)
        final_ctc = float(_ctc_loss(
            final_logits, target_ids, input_lengths, target_lengths
        ).item())
        final_l2 = float(best_delta.norm(p=2).item())

    cancelled = cancel_event is not None and cancel_event.is_set()
    success = not cancelled and _normalise_text(final_text) == target_normalised
    adversarial_waveform = _restore_waveform_scale(
        final_adv_input.squeeze(0), waveform, wrapper
    ).detach()
    perturbation_waveform = adversarial_waveform - waveform

    results_dict: dict = {
        "success": success,
        "final_transcription": final_text,
        "total_iterations": completed_iterations,
        "final_ctc_loss": final_ctc,
        "final_l2_norm": final_l2,
        "restarts_completed": restarts_completed,
        "success_found": success_found,
    }

    logger.info(
        "PGD attack finished id=%s success=%s final_text=%r ctc=%.4f "
        "l2=%.4f iterations=%d",
        attack_id,
        success,
        final_text,
        final_ctc,
        final_l2,
        completed_iterations,
    )

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return adversarial_waveform, perturbation_waveform.detach(), results_dict
