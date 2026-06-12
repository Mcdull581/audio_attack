"""
Wav2Vec2CTC wrapper — loads a frozen HuggingFace model, exposes encode / get_logits /
decode / encode_text for the CW adversarial attack engine.
"""

from __future__ import annotations

import logging
from typing import Optional

import torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

from ..config import DEVICE, MODEL_NAME

logger = logging.getLogger(__name__)


class Wav2Vec2Wrapper:
    """Frozen Wav2Vec2 CTC model with convenience helpers for attack orchestration."""

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        device: Optional[torch.device] = None,
    ) -> None:
        self.model_name = model_name
        self.device = device or DEVICE

        logger.info("Loading Wav2Vec2ForCTC  %s  →  %s", model_name, self.device)
        self.model = Wav2Vec2ForCTC.from_pretrained(model_name).to(self.device)
        self.processor = Wav2Vec2Processor.from_pretrained(model_name)

        # ── freeze all parameters ────────────────────────────────────────
        for param in self.model.parameters():
            param.requires_grad = False

        self.model.eval()
        logger.info("Wav2Vec2Wrapper ready  (params frozen, eval mode)")

    # ── encode raw waveform ────────────────────────────────────────────────

    def encode(
        self, waveform: torch.Tensor, sample_rate: int = 16000
    ) -> dict[str, torch.Tensor]:
        """Run the processor on *waveform*, return input_values & attention_mask."""
        # Move to CPU for the HF processor (which uses numpy internally).
        wav_cpu = waveform.detach().cpu()
        inputs = self.processor(
            wav_cpu, sampling_rate=sample_rate, return_tensors="pt"
        )
        return {k: v.to(self.device) for k, v in inputs.items()}

    # ── forward pass  ──────────────────────────────────────────────────────

    def get_logits(
        self,
        input_values: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Forward pass.  Returns raw logits with gradient path intact for delta
        (model params are frozen so they receive *no* gradients)."""
        outputs = self.model(input_values, attention_mask=attention_mask)
        return outputs.logits  # (batch, time, vocab)

    # ── decode logits → text ───────────────────────────────────────────────

    def decode(self, logits: torch.Tensor) -> str:
        """Argmax → token IDs → processor.batch_decode → text string."""
        predicted_ids = torch.argmax(logits, dim=-1)
        transcriptions = self.processor.batch_decode(predicted_ids)
        return transcriptions[0] if isinstance(transcriptions, list) else transcriptions

    # ── encode target text → token IDs ─────────────────────────────────────

    def encode_text(self, text: str) -> torch.Tensor:
        """Tokenize *text* into CTC target token IDs (no BOS/EOS padding)."""
        tokens = self.processor.tokenizer(text, return_tensors="pt")
        return tokens.input_ids.to(self.device)
