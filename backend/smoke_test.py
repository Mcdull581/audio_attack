"""Live REST/WebSocket smoke test for a running local backend.

Run from the repository root with the Anaconda environment active:
``python backend/smoke_test.py``
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request

import websockets


BASE_URL = "http://127.0.0.1:28000"
SMOKE_MAX_ITERATIONS = int(os.getenv("AUDIO_ATTACK_SMOKE_MAX_ITERATIONS", "100"))
SMOKE_RESTARTS = int(os.getenv("AUDIO_ATTACK_SMOKE_RESTARTS", "3"))
SMOKE_TARGET = os.getenv("AUDIO_ATTACK_SMOKE_TARGET", "hello world")
SMOKE_LEARNING_RATE = float(os.getenv("AUDIO_ATTACK_SMOKE_LEARNING_RATE", "0.001"))
SMOKE_LAMBDA = float(os.getenv("AUDIO_ATTACK_SMOKE_LAMBDA", "0.02"))
SMOKE_EPSILON = float(os.getenv("AUDIO_ATTACK_SMOKE_EPSILON", "0.02"))
SMOKE_MOMENTUM = float(os.getenv("AUDIO_ATTACK_SMOKE_MOMENTUM", "0.9"))


def request_json(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        BASE_URL + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


async def main() -> int:
    samples = request_json("/api/samples")
    assert samples["total"] > 0, "sample list is empty"
    sample_name = samples["samples"][0]["name"]

    try:
        request_json("/api/attack/start", "POST", {"sample_name": "missing", "target_phrase": "hello"})
    except urllib.error.HTTPError as exc:
        assert exc.code == 404, exc.code
    else:
        raise AssertionError("missing sample should return 404")

    created = request_json(
        "/api/attack/start",
        "POST",
        {
            "sample_name": sample_name,
            "target_phrase": SMOKE_TARGET,
            "epsilon": SMOKE_EPSILON,
            "max_iterations": SMOKE_MAX_ITERATIONS,
            "lambda_l2": SMOKE_LAMBDA,
            "learning_rate": SMOKE_LEARNING_RATE,
            "momentum": SMOKE_MOMENTUM,
            "restarts": SMOKE_RESTARTS,
        },
    )
    attack_id = created["attack_id"]
    uri = f"ws://127.0.0.1:28000/ws/attack/{attack_id}"
    message_types: list[str] = []
    complete: dict | None = None
    last_progress: dict | None = None

    async with websockets.connect(uri, open_timeout=30, close_timeout=30) as socket:
        async for raw in socket:
            message = json.loads(raw)
            message_types.append(message.get("type", ""))
            if message.get("type") == "iteration_progress":
                last_progress = message
            if message.get("type") in {"attack_complete", "attack_error"}:
                complete = message
                break

    assert "attack_started" in message_types
    assert "iteration_progress" in message_types
    assert complete is not None
    assert complete["type"] == "attack_complete", complete
    assert 0 <= complete["total_iterations"] <= SMOKE_MAX_ITERATIONS * SMOKE_RESTARTS
    assert complete.get("cancelled") is False
    for key in ("original_wav_url", "adversarial_wav_url", "perturbation_wav_url"):
        output_url = BASE_URL + complete["resources"][key]
        with urllib.request.urlopen(output_url, timeout=30) as response:
            assert response.status == 200

    print(json.dumps({
        "sample_total": samples["total"],
        "attack_id": attack_id,
        "messages": message_types,
        "success": complete["success"],
        "final_transcription": complete["final_transcription"],
        "last_progress": {
            "iteration": last_progress.get("iteration") if last_progress else None,
            "ctc_loss": last_progress.get("ctc_loss") if last_progress else None,
            "snr_db": last_progress.get("snr_db") if last_progress else None,
            "current_transcription": last_progress.get("current_transcription") if last_progress else None,
        },
        "total_iterations": complete["total_iterations"],
        "restarts": created["config"]["restarts"],
        "outputs_http_200": True,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except (AssertionError, OSError, urllib.error.URLError) as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
