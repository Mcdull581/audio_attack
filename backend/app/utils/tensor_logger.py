"""
Lightweight tensor-snapshot serialization utilities.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch

logger = logging.getLogger(__name__)


def tensor_to_list(t: torch.Tensor) -> list:
    """Flatten a 1-D tensor into a Python list (for edge-case serialisation)."""
    return t.detach().cpu().flatten().tolist()


def _sanitise_value(v: Any) -> Any:
    """Recursively convert non-JSON-serialisable values (tensors, …)."""
    if isinstance(v, torch.Tensor):
        if v.numel() == 1:
            return v.item()
        return tensor_to_list(v)
    if isinstance(v, (list, tuple)):
        return [_sanitise_value(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _sanitise_value(val) for k, val in v.items()}
    return v


def serialize_progress_entry(entry: dict) -> dict:
    """Return a deep copy of *entry* with every value JSON-serialisable."""
    return _sanitise_value(entry)


def log_iteration_to_file(entry: dict, log_path: str) -> None:
    """Append one JSON line (serialised *entry*) to *log_path*."""
    sanitised = serialize_progress_entry(entry)
    try:
        p = Path(log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            json.dump(sanitised, fh, ensure_ascii=False)
            fh.write("\n")
    except Exception:
        logger.exception("Failed to write iteration log to %s", log_path)
