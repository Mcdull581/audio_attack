"""
Global configuration and shared type contracts for the CW attack lab.
All modules import from here to ensure interface consistency.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Literal, Optional, TypedDict

import pydantic

# ── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = PROJECT_ROOT / "data" / "sampled"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Model & Dataset ──────────────────────────────────────────────────────
MODEL_NAME: str = "facebook/wav2vec2-base-960h"
DATASET_NAME: str = "mozilla-foundation/common_voice_25_0"
DATASET_CONFIG: str = "en"
DATASET_SPLIT: str = "test"
DATASET_REVISION: Optional[str] = None  # pin to a specific commit if needed

SAMPLE_RATE: int = 16000
NUM_SAMPLES: int = 100
MIN_DURATION_SEC: float = 1.0
MAX_DURATION_SEC: float = 15.0

# ── Attack Defaults ──────────────────────────────────────────────────────
DEFAULT_EPSILON: float = 0.01
DEFAULT_MAX_ITER: int = 1000
DEFAULT_LAMBDA_L2: float = 0.1
DEFAULT_LEARNING_RATE: float = 5e-4

# ── Computation device selection ─────────────────────────────────────────
import torch

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# Startup verification
if DEVICE.type == "cuda":
    _props = torch.cuda.get_device_properties(0)
    print(f"[CONFIG] CUDA ENABLED: {_props.name} ({_props.total_memory // 1024**2} MiB VRAM)")
else:
    print("[CONFIG] WARNING: CUDA not available — running on CPU (expect slow training)")

# ── Attack State Machine ─────────────────────────────────────────────────
class AttackStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── WebSocket Message Type Literals ──────────────────────────────────────
WSMsgType = Literal[
    "attack_started",
    "iteration_progress",
    "attack_complete",
    "attack_error",
]


# ══════════════════════════════════════════════════════════════════════════
# Pydantic Models  (REST request / response)
# ══════════════════════════════════════════════════════════════════════════

class AttackConfigIn(pydantic.BaseModel):
    """Incoming attack configuration from the frontend."""
    sample_name: str
    target_phrase: str = "hello world"
    epsilon: float = DEFAULT_EPSILON
    max_iterations: int = DEFAULT_MAX_ITER
    lambda_l2: float = DEFAULT_LAMBDA_L2
    learning_rate: float = DEFAULT_LEARNING_RATE

    @pydantic.field_validator("epsilon")
    @classmethod
    def epsilon_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("epsilon must be > 0")
        return v

    @pydantic.field_validator("max_iterations")
    @classmethod
    def max_iter_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_iterations must be >= 1")
        return v

    @pydantic.field_validator("target_phrase")
    @classmethod
    def target_not_empty(cls, v: str) -> str:
        stripped = v.strip().lower()
        if not stripped:
            raise ValueError("target_phrase must not be empty")
        return stripped


class AttackResponse(pydantic.BaseModel):
    """Response after accepting an attack request."""
    attack_id: str
    status: AttackStatus
    config: AttackConfigIn


class SampleInfo(pydantic.BaseModel):
    """Metadata for a single cached audio sample."""
    name: str
    local_path: str
    duration_sec: float
    transcription: str


class SampleListResponse(pydantic.BaseModel):
    """Response for GET /api/samples."""
    samples: list[SampleInfo]
    total: int


class ErrorResponse(pydantic.BaseModel):
    detail: str
    error_code: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════
# WebSocket Message Schemas (plain dicts for JSON serialization)
# ══════════════════════════════════════════════════════════════════════════

class WsEnvelope(TypedDict, total=False):
    type: WSMsgType
    attack_id: str


class AttackStartedMsg(WsEnvelope):
    type: Literal["attack_started"]
    config: dict          # AttackConfigIn serialized
    original_transcription: str
    audio_duration_sec: float
    push_interval: int


class IterationProgressMsg(WsEnvelope):
    type: Literal["iteration_progress"]
    iteration: int
    ctc_loss: float
    l2_loss: float
    total_loss: float
    l2_norm_delta: float
    snr_db: float
    current_transcription: str
    target_transcription: str
    timestamp: float  # time.monotonic() or time.time()


class AttackCompleteMsg(WsEnvelope):
    type: Literal["attack_complete"]
    total_iterations: int
    final_ctc_loss: float
    final_l2_norm: float
    final_transcription: str
    target_transcription: str
    success: bool
    resources: dict  # {"original_wav_url": ..., "adversarial_wav_url": ..., "perturbation_wav_url": ...}


class AttackErrorMsg(WsEnvelope):
    type: Literal["attack_error"]
    error_code: str
    message: str
    timestamp: float


# Union for type-narrowing helpers
WsMessage = AttackStartedMsg | IterationProgressMsg | AttackCompleteMsg | AttackErrorMsg


# ══════════════════════════════════════════════════════════════════════════
# Internal Engine Dataclass
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class AttackJob:
    """In-memory representation of an active attack job."""
    attack_id: str
    config: AttackConfigIn
    status: AttackStatus = AttackStatus.QUEUED
    original_transcription: str = ""
    waveform_path: str = ""
    adversarial_path: str = ""
    delta_path: str = ""
    iteration_history: list[dict] = field(default_factory=list)

    def push_interval(self) -> int:
        return max(1, self.config.max_iterations // 200)

    def result_urls(self) -> dict:
        base = f"/api/audio/download"
        return {
            "original_wav_url": f"{base}/original/{self.attack_id}.wav",
            "adversarial_wav_url": f"{base}/adversarial/{self.attack_id}.wav",
            "perturbation_wav_url": f"{base}/delta/{self.attack_id}.wav",
        }
