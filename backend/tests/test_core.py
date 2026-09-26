"""Fast, dependency-light regression tests for the backend contracts."""

from __future__ import annotations

import json
import threading
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import soundfile as sf
import torch

from app.config import AttackConfigIn, AttackJob, AttackStatus
from app.engine import attack as attack_engine
from app.engine import loader
from app.engine.model import Wav2Vec2Wrapper


class BackendContractTests(unittest.TestCase):
    def test_model_target_text_matches_uppercase_ctc_vocabulary(self) -> None:
        class FakeTokenizer:
            def __init__(self) -> None:
                self.received = ""

            def __call__(self, text: str, return_tensors: str) -> SimpleNamespace:
                self.received = text
                return SimpleNamespace(input_ids=torch.tensor([[1]], dtype=torch.long))

        tokenizer = FakeTokenizer()
        wrapper = object.__new__(Wav2Vec2Wrapper)
        wrapper.device = torch.device("cpu")
        wrapper.processor = SimpleNamespace(tokenizer=tokenizer)

        wrapper.encode_text("hello world")

        self.assertEqual(tokenizer.received, "HELLO WORLD")

    def test_attack_config_normalizes_target_and_rejects_invalid_epsilon(self) -> None:
        config = AttackConfigIn(sample_name="clip", target_phrase="  Hello World ")
        self.assertEqual(config.target_phrase, "hello world")

        with self.assertRaises(ValueError):
            AttackConfigIn(sample_name="clip", epsilon=0)


    def test_attack_job_urls_and_push_interval(self) -> None:
        job = AttackJob(
            attack_id="abc",
            config=AttackConfigIn(sample_name="clip", max_iterations=1000),
            status=AttackStatus.QUEUED,
        )
        self.assertEqual(job.push_interval(), 15)
        self.assertTrue(job.result_urls()["adversarial_wav_url"].endswith("/adversarial/abc.wav"))

    def test_pgd_defaults_and_restart_validation(self) -> None:
        config = AttackConfigIn(sample_name="clip")
        self.assertEqual(config.restarts, 3)
        self.assertAlmostEqual(config.momentum, 0.9)
        self.assertAlmostEqual(config.learning_rate, 1e-3)

        with self.assertRaises(ValueError):
            AttackConfigIn(sample_name="clip", restarts=0)
        with self.assertRaises(ValueError):
            AttackConfigIn(sample_name="clip", momentum=1.0)


    def test_force_scan_preserves_existing_transcription(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sampled = root / "sampled"
            sampled.mkdir()
            sf.write(sampled / "clip.wav", np.zeros(16000, dtype=np.float32), 16000)
            manifest_path = root / "samples_manifest.json"
            manifest_path.write_text(
                json.dumps([{"name": "clip", "transcription": "cached text"}]),
                encoding="utf-8",
            )

            with patch.object(loader, "DATA_DIR", sampled), patch.object(loader, "MANIFEST_PATH", manifest_path):
                result = loader.prepare_samples(force=True)

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["transcription"], "cached text")
            self.assertEqual(json.loads(manifest_path.read_text(encoding="utf-8"))[0]["name"], "clip")


class _FakeFeatureExtractor:
    do_normalize = False


class _FakeProcessor:
    feature_extractor = _FakeFeatureExtractor()


class _FakeModel:
    def _get_feat_extract_output_lengths(self, input_length: int) -> int:
        return 2


class _FakeWrapper:
    device = torch.device("cpu")
    processor = _FakeProcessor()
    model = _FakeModel()

    def encode_text(self, text: str) -> torch.Tensor:
        return torch.tensor([[1]], dtype=torch.long)

    def encode(self, waveform: torch.Tensor, sample_rate: int = 16000) -> dict[str, torch.Tensor]:
        return {"input_values": waveform.reshape(1, -1)}

    def get_logits(self, input_values: torch.Tensor, attention_mask=None) -> torch.Tensor:
        value = input_values.mean()
        return torch.stack((value, -value, value), dim=0).reshape(1, 1, 3).repeat(1, 2, 1)

    def decode(self, logits: torch.Tensor) -> str:
        return ""


class AttackEngineTests(unittest.TestCase):
    def test_cancelled_attack_returns_actual_iteration_count_and_matching_shapes(self) -> None:
        cancel_event = threading.Event()
        cancel_event.set()
        waveform = torch.zeros(16000, dtype=torch.float32)

        adversarial, delta, result = attack_engine.run_cw_attack_sync(
            waveform=waveform,
            sample_rate=16000,
            target_phrase="a",
            wrapper=_FakeWrapper(),
            config_dict={
                "epsilon": 0.01,
                "max_iterations": 10,
                "lambda_l2": 0.1,
                "learning_rate": 5e-4,
                "cancel_event": cancel_event,
            },
            progress_callback=lambda _: None,
        )

        self.assertEqual(result["total_iterations"], 0)
        self.assertFalse(result["success"])
        self.assertEqual(adversarial.shape, waveform.shape)
        self.assertEqual(delta.shape, waveform.shape)


if __name__ == "__main__":
    unittest.main()
