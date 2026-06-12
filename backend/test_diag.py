"""Diagnostic: test model forward pass on a local audio file."""
import sys
sys.path.insert(0, ".")

from app.engine.model import Wav2Vec2Wrapper
from app.engine.attack import run_cw_attack_sync
from app.utils.audio_io import load_wav
from pathlib import Path

print("Loading model...")
wrapper = Wav2Vec2Wrapper()
print("Model loaded.")

wav_path = Path("data/sampled/common_voice_en_10.mp3")
waveform, sr = load_wav(str(wav_path))
print(f"Audio: shape={waveform.shape}, sr={sr}")

# Forward pass
encoded = wrapper.encode(waveform, sample_rate=sr)
print(f"Encoded: shape={encoded['input_values'].shape}")

logits = wrapper.get_logits(encoded["input_values"])
print(f"Logits: shape={logits.shape}")

text = wrapper.decode(logits)
print(f"Decoded: {text!r}")

# Try running a short attack
print("\nRunning short attack (10 iter)...")
def cb(msg):
    t = msg.get("type", "")
    if t == "iteration_progress":
        print(f"  [{msg['iteration']:3d}] ctc={msg['ctc_loss']:.4f} l2={msg['l2_loss']:.4f} SNR={msg['snr_db']:.1f} text={msg['current_transcription']!r}")

try:
    adv, delta, results = run_cw_attack_sync(
        waveform=waveform,
        sample_rate=sr,
        target_phrase="hello world",
        wrapper=wrapper,
        config_dict={"epsilon": 0.005, "max_iterations": 10, "lambda_l2": 0.1, "learning_rate": 5e-4, "attack_id": "diag"},
        progress_callback=cb,
    )
    print(f"\nResults: success={results['success']}, final={results['final_transcription']!r}")
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
