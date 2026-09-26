# Audio Adversarial Attack Lab

**White-Box Adversarial Attack Visualization Lab** — Targeted PGD + momentum attacks against `facebook/wav2vec2-base-960h` end-to-end speech recognition, using the Carlini & Wagner (2018) CTC/L2 objective.

Real-time visualization of gradient backpropagation via Web UI: iterative loss curves, waveform/spectrogram comparison, ASR transcription convergence.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (Vue 3 + Vite)                      │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │ REST     │  │ WebSocket    │  │ Audio Player (wavesurfer) │ │
│  │ (Axios)  │  │ (Native API) │  │ Original vs Adversarial   │ │
│  └────┬─────┘  └──────┬───────┘  └─────────────┬─────────────┘ │
│       │               │                        │               │
│  ┌────┴───────────────┴────────────────────────┴─────────────┐ │
│  │  Pinia stores + Composables + ECharts + wavesurfer.js     │ │
│  └───────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           │  HTTP/1.1 + WebSocket
┌──────────────────────────┴──────────────────────────────────────┐
│                   Backend (FastAPI + PyTorch)                    │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ REST /api/* │  │ WS /ws/*     │  │ Static /data/*         │ │
│  └──────┬──────┘  └──────┬───────┘  └───────────┬────────────┘ │
│         │                │                       │              │
│  ┌──────┴────────────────┴───────────────────────┴────────────┐ │
│  │                   PGD Attack Engine                         │ │
│  │  Wav2Vec2 (frozen) │ Momentum PGD │ CTC/L2 + restarts      │ │
│  │  Data: local scan → 246 clips → 16kHz mono wav             │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Communication

| Channel | Content | Direction |
|---------|---------|-----------|
| `REST` | Sample list, attack config, wav download | C↔S |
| `WebSocket` | Iteration progress JSON, transcription, terminal state | S→C |
| `Static` | Local wav files via HTTP | S→C |

**No HTTP polling** — all training progress via WebSocket.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Vue 3 (Composition API) + Vite + TailwindCSS 3 |
| **Charts** | ECharts 5 |
| **Waveform** | wavesurfer.js 7 |
| **State** | Pinia 2 |
| **Backend** | FastAPI + Uvicorn |
| **ML** | PyTorch 2.3 + torchaudio + HuggingFace transformers |
| **Target Model** | `facebook/wav2vec2-base-960h` (Wav2Vec2ForCTC) |
| **GPU** | CUDA 12.4 (RTX 5070 Ti compatible) |
| **Docker** | nvidia/cuda:12.4.0-runtime-ubuntu22.04 |

---

## Quick Start

### 1. Backend (Anaconda)

```bash
conda env create -f environment.yml
conda activate audio-attack
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 28000
```

The model loader is local-cache-only by default. Set `AUDIO_ATTACK_LOCAL_ONLY=0` only when a model download is intended.

The lifespan handler will:
1. Load the Wav2Vec2 model into memory
2. Scan `backend/data/sampled/` for local audio files
3. Generate `samples_manifest.json`

> Place audio files in `backend/data/sampled/`. Run `curl -X POST http://localhost:28000/api/samples/preload` to force a rescan while preserving existing transcriptions.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies:
- `/api/*` → `http://localhost:28000`
- `/ws/*` → `ws://localhost:28000`
- `/data/*` → `http://localhost:28000`

### 3. Docker (Optional)

```bash
cd backend
docker build -t audio-attack-lab .
docker run --gpus all -p 28000:28000 audio-attack-lab
```

---

## Usage

1. Open `http://localhost:5173`
2. **Sample List** (left) → click a sample
3. **Attack Panel** (left) → enter target phrase, set params
4. Click **Start Attack** → real-time monitoring begins
5. Watch **Loss Curve** (right) — CTC Loss, L2 Norm, SNR
6. After completion → download adversarial audio, compare waveforms

---

## Attack Algorithm

Targeted momentum-PGD attack for CTC-based ASR:

```
Minimize:  CTC_Loss(f(x + δ), y_target) + λ · ‖δ‖₂
Subject to: ‖δ‖∞ ≤ ε
```

- **Optimizer**: normalized-gradient momentum PGD, step size = 1e-3
- **Restarts**: one zero start plus two random starts by default
- **Best candidate**: exact match, then edit distance, then CTC loss
- **Constraint**: `clamp(δ, -ε, ε)` after each step
- **Early stopping**: stop immediately when greedy decoding matches the target
- **Convergence**: `decode(argmax(logits)) == target_phrase`

---

## API Reference

### REST

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/samples` | List all cached samples |
| `POST` | `/api/samples/preload` | Trigger dataset scan |
| `POST` | `/api/attack/start` | Create AttackJob (queued) |
| `GET` | `/api/attack/{id}/status` | Query attack status |
| `POST` | `/api/attack/{id}/cancel` | Cooperatively cancel an attack |
| `GET` | `/api/audio/download/{type}/{filename}` | Download wav |

### WebSocket

| Message | Direction | Payload |
|---------|-----------|---------|
| `attack_started` | S→C | config, original_transcription, total_iterations_budget |
| `iteration_progress` | S→C | iteration, restart_index, ctc_loss, l2_loss, snr_db, transcription |
| `attack_complete` | S→C | success, final_transcription, resource URLs |
| `attack_error` | S→C | error_code, message |

---

## Key Features

| Feature | Detail |
|---------|--------|
| **Graceful Cancellation** | WS disconnect → `threading.Event` stops attack loop immediately |
| **GPU Cleanup** | `gc.collect()` + `torch.cuda.empty_cache()` after each attack |
| **Local Audio** | Scans `sampled/` for `.mp3/.wav/.flac` — no network needed |
| **Auto Resample** | All audio → 16kHz mono via soundfile + torchaudio |

---

## Configuration

All in `backend/app/config.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `facebook/wav2vec2-base-960h` | Target model |
| `SAMPLE_RATE` | 16000 | Audio sample rate |
| `DEFAULT_EPSILON` | 0.02 | Perturbation budget |
| `DEFAULT_MAX_ITER` | 1000 | Max iterations |
| `DEFAULT_LAMBDA_L2` | 0.02 | L2 regularization |
| `DEFAULT_LEARNING_RATE` | 1e-3 | PGD step size |
| `DEFAULT_MOMENTUM` | 0.9 | Momentum coefficient |
| `DEFAULT_RESTARTS` | 3 | Number of starts |
| `MIN_DURATION_SEC` | 1.0 | Min audio clip duration |
| `MAX_DURATION_SEC` | 15.0 | Max audio clip duration |

---

## Research

> Carlini, N., & Wagner, D. (2018). *Audio Adversarial Examples: Targeted Attacks on Speech-to-Speech.* IEEE S&PW.

- Baevski et al. (2020). *wav2vec 2.0.* NeurIPS.
- Graves et al. (2006). *Connectionist Temporal Classification.* ICML.
- Mozilla Common Voice. https://commonvoice.mozilla.org/

---

## Build Verification

| Layer | Command | Result |
|-------|---------|--------|
| Backend | `python -m py_compile` (16 files) | ✅ 0 errors |
| Frontend | `npm run build` (vue-tsc + vite) | ✅ 0 errors |

---

## License

MIT — Academic use only.
