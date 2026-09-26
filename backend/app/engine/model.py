"""
Wav2Vec2CTC wrapper — loads a frozen HuggingFace model, exposes encode / get_logits /
decode / encode_text for the CW adversarial attack engine.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import torch
from transformers import Wav2Vec2Config, Wav2Vec2ForCTC, Wav2Vec2Processor
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file

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
        # This application ships/uses a local model cache and should not spend
        # several minutes retrying blocked Hugging Face HEAD requests during
        # every startup.  Set AUDIO_ATTACK_LOCAL_ONLY=0 only when a network
        # download is explicitly desired.
        local_only = os.getenv("AUDIO_ATTACK_LOCAL_ONLY", "1").lower() not in {
            "0", "false", "no",
        }
        self.model = self._load_model(model_name, local_only).to(self.device)
        self.processor = Wav2Vec2Processor.from_pretrained(
            model_name, local_files_only=local_only
        )

        # SpecAugment is a training-time transform.  Leaving it enabled makes
        # inference and the attack stochastic, and this checkpoint does not
        # contain a trained masked-spec embedding.  Disable it for stable ASR.
        self.model.config.apply_spec_augment = False

        # ── freeze all parameters ────────────────────────────────────────
        for param in self.model.parameters():
            param.requires_grad = False

        self.model.eval()
        logger.info("Wav2Vec2Wrapper ready  (params frozen, eval mode)")

    def _load_model(self, model_name: str, local_only: bool) -> Wav2Vec2ForCTC:
        """Load a checkpoint while normalizing legacy torch weight-norm keys."""
        checkpoint = hf_hub_download(
            repo_id=model_name,
            filename="model.safetensors",
            local_files_only=local_only,
        )
        config = Wav2Vec2Config.from_pretrained(
            model_name, local_files_only=local_only
        )
        model = Wav2Vec2ForCTC(config)
        state = load_file(checkpoint, device="cpu")

        legacy_prefix = "wav2vec2.encoder.pos_conv_embed.conv."
        for old_name, new_name in (
            (legacy_prefix + "weight_g", legacy_prefix + "parametrizations.weight.original0"),
            (legacy_prefix + "weight_v", legacy_prefix + "parametrizations.weight.original1"),
        ):
            if old_name in state:
                state[new_name] = state.pop(old_name)

        missing, unexpected = model.load_state_dict(state, strict=False)
        expected_missing = {"wav2vec2.masked_spec_embed"}
        real_missing = [name for name in missing if name not in expected_missing]
        if real_missing or unexpected:
            raise RuntimeError(
                f"Checkpoint/model mismatch; missing={real_missing}, unexpected={unexpected}"
            )
        logger.info("Loaded checkpoint weights with torch-compatible key mapping")
        return model

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
        """Tokenize *text* into CTC target IDs (no BOS/EOS padding).

        The bundled Wav2Vec2 CTC vocabulary contains uppercase letters. The
        API keeps targets lower-case for stable display/comparison, so the
        model-facing text must be upper-cased here; otherwise every letter in
        a lower-case target becomes ``<unk>`` and the attack optimizes the
        wrong sequence.
        """
        tokens = self.processor.tokenizer(text.upper(), return_tensors="pt")
        return tokens.input_ids.to(self.device)
