"""
WebSocket test client — connects to an attack and displays real-time progress.
Usage: python test_ws.py <attack_id>
"""
import asyncio
import json
import sys
import websockets


async def monitor_attack(attack_id: str):
    uri = f"ws://localhost:8000/ws/attack/{attack_id}"
    print(f"Connecting to {uri} ...\n")

    try:
        async with websockets.connect(uri) as ws:
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "attack_started":
                    print(f"[STARTED] target={msg['config']['target_phrase']!r} "
                          f"duration={msg['audio_duration_sec']:.1f}s "
                          f"push_interval={msg['push_interval']}")
                    print(f"[ORIG]   transcription={msg['original_transcription']!r}")
                    print("-" * 60)

                elif msg_type == "iteration_progress":
                    bar_len = 30
                    max_iter = msg.get("config", {}).get("max_iterations", 1000)
                    pct = min(1.0, msg["iteration"] / max(max_iter, 1))
                    filled = int(bar_len * pct)
                    bar = "#" * filled + "-" * (bar_len - filled)
                    print(f"\r[{bar}] iter={msg['iteration']:4d} "
                          f"ctc={msg['ctc_loss']:8.4f} "
                          f"l2={msg['l2_loss']:7.4f} "
                          f"snr={msg['snr_db']:6.1f}dB "
                          f"text={msg['current_transcription']!r}", end="", flush=True)

                elif msg_type == "attack_complete":
                    print(f"\n{'-'*60}")
                    success = msg.get("success", False)
                    final = msg.get("final_transcription", "")
                    print(f"[{'SUCCESS' if success else 'INCOMPLETE'}] "
                          f"final={final!r} "
                          f"target={msg.get('target_transcription')!r} "
                          f"iter={msg['total_iterations']} "
                          f"ctc={msg['final_ctc_loss']:.4f} "
                          f"l2={msg['final_l2_norm']:.4f}")
                    print(f"[FILES] adv={msg['resources']['adversarial_wav_url']}")
                    break

                elif msg_type == "attack_error":
                    print(f"\n[ERROR] {msg['error_code']}: {msg['message']}")
                    break

    except (OSError, ConnectionRefusedError) as e:
        print(f"Connection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_ws.py <attack_id>")
        print("Example: python test_ws.py 3ca87b98-b4d3-4871-a25e-809830b92b5d")
        sys.exit(1)
    asyncio.run(monitor_attack(sys.argv[1]))
