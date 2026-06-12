# Audio Adversarial Attack Lab

**白盒对抗攻击可视化实验室** — 针对 `facebook/wav2vec2-base-960h` 端到端语音识别模型的 Carlini & Wagner (2018) 定向攻击复现平台。

通过 Web UI 将张量反向传播过程实时可视化：迭代 loss 曲线、波形/语谱图对比、ASR 转录收敛演示。

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (Vue 3 + Vite)                      │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │ REST     │  │ WebSocket    │  │ Audio Player (wavesurfer) │ │
│  │ (Axios)  │  │ (原生 API)    │  │ 原始 vs 对抗双轨对比       │ │
│  └────┬─────┘  └──────┬───────┘  └─────────────┬─────────────┘ │
│       │               │                        │               │
│  ┌────┴───────────────┴────────────────────────┴─────────────┐ │
│  │  Pinia stores (attackStore, audioStore) + Composables     │ │
│  │  ECharts loss curve / wavesurfer.js waveform / typing TXT │ │
│  └───────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           │  HTTP/1.1 + WebSocket
┌──────────────────────────┴──────────────────────────────────────┐
│                   Backend (FastAPI + PyTorch)                    │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ REST /api/* │  │ WS /ws/*     │  │ Static /data/*         │ │
│  │ 样本列表     │  │ 实时进度推送  │  │ wav 文件下载            │ │
│  │ 攻击配置     │  │ loss / SNR   │  │                        │ │
│  │ 音频下载     │  │ 转录收敛过程  │  │                        │ │
│  └──────┬──────┘  └──────┬───────┘  └───────────┬────────────┘ │
│         │                │                       │              │
│  ┌──────┴────────────────┴───────────────────────┴────────────┐ │
│  │                    CW Attack Engine                         │ │
│  │  ┌──────────────┐  ┌────────────┐  ┌────────────────────┐  │ │
│  │  │ Wav2Vec2     │  │ Adam Opt   │  │ CTC Loss + L2 Norm │  │ │
│  │  │ (frozen)     │  │ on δ       │  │ δ ∈ [-ε, ε]       │  │ │
│  │  └──────────────┘  └────────────┘  └────────────────────┘  │ │
│  │                                                             │ │
│  │  Data Pipeline: HF datasets (streaming) → 100 clips → wav  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 通信协议

| 通道 | 承载内容 | 方向 |
|------|---------|------|
| `REST` | 样本列表、攻击配置提交、wav 下载 | C↔S |
| `WebSocket` | 迭代进度 JSON（每 N 步推送）、转录收敛、终态 | S→C |
| `Static` | 落盘 wav 文件直接 HTTP 访问 | S→C |

**严禁 HTTP 轮询** — 实时训练进度均通过 WebSocket 长连接推送。

---

## Tech Stack

| 层级 | 技术 | 版本 |
|------|------|------|
| **Frontend** | Vue 3 (Composition API) + Vite + TailwindCSS 3 | — |
| **Charts** | ECharts 5 (双折线 loss 曲线) | — |
| **Waveform** | wavesurfer.js 7 (双轨音频可视化) | — |
| **State** | Pinia 2 | — |
| **Backend** | FastAPI + Uvicorn | ≥0.111 |
| **ML** | PyTorch 2.3 + torchaudio + HuggingFace transformers | ≥2.3 |
| **Target Model** | `facebook/wav2vec2-base-960h` (Wav2Vec2ForCTC) | HF |
| **Dataset** | `mozilla-foundation/common_voice_25_0` (en, test) | HF streaming |
| **GPU** | CUDA 12.4 (RTX 5070 Ti / compatible) | — |
| **Container** | Docker (nvidia/cuda:12.4.0-runtime-ubuntu22.04) | — |

---

## Project Structure

```
audio_attack/
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── .gitignore
│   ├── app/
│   │   ├── config.py                 # 全局配置、Pydantic 模型、WS 消息类型契约
│   │   ├── main.py                   # FastAPI 入口：CORS、lifespan、路由挂载
│   │   ├── api/
│   │   │   ├── rest.py               # REST 端点（/api/samples, /api/attack/*, /api/audio/*）
│   │   │   ├── ws.py                 # WebSocket 端点（/ws/attack/{id}）+ 线程桥接
│   │   │   └── websocket_manager.py  # ConnectionManager（WS 连接生命周期）
│   │   ├── engine/
│   │   │   ├── model.py              # Wav2Vec2Wrapper（冻结权重、encode/decode/logits）
│   │   │   ├── attack.py             # run_cw_attack_sync（CW 攻击核心循环）
│   │   │   ├── optimizer.py          # Adam 优化器 + clamp + SNR 计算
│   │   │   ├── loader.py             # HF datasets 流式加载 → 100 条 wav 落盘
│   │   │   └── preprocess.py         # 重采样(16kHz)、能量裁剪(3-5s)、归一化
│   │   └── utils/
│   │       ├── audio_io.py           # torchaudio wav 读写
│   │       └── tensor_logger.py      # 张量序列化
│   ├── data/
│   │   └── sampled/                  # 100 条采样的 16kHz wav 文件 (.gitignore)
│   └── tests/
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts              # dev proxy → backend
    ├── tailwind.config.ts          # dark mode, custom colors
    ├── tsconfig.json
    ├── tsconfig.node.json
    ├── postcss.config.js
    └── src/
        ├── main.ts                   # Vue 入口
        ├── App.vue                   # 根组件
        ├── assets/styles/
        │   └── tailwind.css          # Tailwind + Dark Mode 变量
        ├── types/
        │   ├── ws.ts                 # WebSocket 消息类型
        │   └── attack.ts             # 攻击配置与结果类型
        ├── stores/
        │   ├── attackStore.ts        # 攻击任务状态（Pinia）
        │   └── audioStore.ts         # 音频缓冲区（Pinia）
        ├── composables/
        │   ├── useWebSocket.ts       # WS 连接 + 自动重连 + 消息分发
        │   ├── useAttack.ts          # 攻击生命周期状态机
        │   └── useAudioPlayer.ts     # wavesurfer.js 双轨播放
        ├── components/
        │   ├── layout/
        │   │   ├── AppShell.vue      # 全局布局（侧栏 + 主区）
        │   │   └── StatusBar.vue     # GPU 状态 / 迭代进度
        │   ├── dashboard/
        │   │   ├── AttackPanel.vue   # 目标短语、ε、迭代次数配置
        │   │   └── SampleList.vue    # 数据集样本选择
        │   ├── visualization/
        │   │   ├── WaveformView.vue  # 原始 vs 对抗波形（wavesurfer.js）
        │   │   ├── SpectrogramView.vue # 语谱图对比
        │   │   └── LossCurve.vue     # 实时 loss 双折线（ECharts）
        │   └── common/
        │       ├── Card.vue
        │       └── MetricBadge.vue
        └── utils/
            └── api.ts                # Axios 实例封装
```

---

## Quick Start

### 1. Prerequisites

- Python 3.10+ with CUDA 12.4 drivers
- Node.js 18+ & npm
- (Optional) Docker + nvidia-container-toolkit

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies (CUDA 12.x torch)
pip install -r requirements.txt

# Pre-download the model (first run will fetch ~360MB)
python -c "from app.engine.model import Wav2Vec2Wrapper; Wav2Vec2Wrapper()"

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

On first startup, the lifespan handler will:
1. Load `facebook/wav2vec2-base-960h` into GPU memory
2. Stream 100 English test clips (3-5s each) from Common Voice 25.0
3. Preprocess and cache them as 16-bit PCM wav files
4. Write `samples_manifest.json` to `backend/data/`

> **Note:** Subsequent starts skip the download — manifest is loaded from cache.

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies /api and /ws to backend:8000)
npm run dev
```

The Vite dev server auto-proxies:
- `/api/*` → `http://localhost:8000`
- `/ws/*` → `ws://localhost:8000` (WebSocket)
- `/data/*` → `http://localhost:8000` (static wav files)

### 4. Docker (Optional)

```bash
cd backend

# Build the CUDA-enabled image
docker build -t audio-attack-lab .

# Run with GPU passthrough
docker run --gpus all -p 8000:8000 audio-attack-lab
```

---

## Usage Workflow

```
1. Open http://localhost:5173 (frontend dev server)
       │
2. Browse sample list → select an audio clip (e.g., "cv_en_00042")
       │
3. Enter target phrase (e.g., "hello world")
       │
4. Set attack parameters:
   - Epsilon (perturbation budget, default: 0.01)
   - Max iterations (default: 1000)
   - Lambda L2 (regularization weight, default: 0.1)
       │
5. Click "Start Attack"
   → REST POST /api/attack/start → returns attack_id
   → Frontend opens WebSocket to /ws/attack/{attack_id}
   → UI locks (prevents double-submit / OOM)
       │
6. Real-time monitoring:
   ┌─────────────────────────────────────────┐
   │ Loss Curve (ECharts):                   │
   │   — CTC Loss (blue)                     │
   │   — L2 Norm (orange)                    │
   │                                         │
   │ Transcription (typewriter effect):      │
   │   Current: "helo world"                 │
   │   Target:  "hello world"                │
   │                                         │
   │ Status Bar:                             │
   │   Iteration: 487/1000 | SNR: 24.7 dB   │
   └─────────────────────────────────────────┘
       │
7. Attack completes → UI unlocks
   → Download adversarial wav / delta wav
   → Compare waveforms side-by-side (wavesurfer.js)
   → Play back original vs adversarial audio
```

---

## Attack Algorithm

实现的是 **Carlini & Wagner (2018)** 针对 CTC-based ASR 的白盒定向攻击：

```
Minimize:  CTC_Loss(f(x + δ), y_target) + λ · ‖δ‖₂
Subject to: ‖δ‖∞ ≤ ε

Where:
  f      = frozen Wav2Vec2ForCTC
  x      = original waveform (16kHz mono)
  δ      = adversarial perturbation
  y_target = target transcription token sequence
  ε      = perturbation budget (L∞ norm bound)
  λ      = L2 regularization weight
```

**优化器**: Adam on δ, learning rate = 5e-4
**约束投影**: 每步后 `clamp(δ, -ε, ε)`
**收敛判断**: `decode(argmax(logits)) == target_phrase`

---

## API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/samples` | 列出所有缓存的音频样本 |
| `POST` | `/api/samples/preload` | 触发数据集下载 |
| `POST` | `/api/attack/start` | 创建 AttackJob（不立即执行） |
| `GET` | `/api/attack/{id}/status` | 查询攻击状态 |
| `GET` | `/api/audio/download/{type}/{filename}` | 下载 wav（original/adversarial/delta）|

### WebSocket Protocol

| Message Type | Direction | Trigger | Payload |
|-------------|-----------|---------|---------|
| `attack_started` | S→C | WS 连接建立 | config, original_transcription, audio_duration_sec |
| `iteration_progress` | S→C | 每 200 次迭代 | iteration, ctc_loss, l2_loss, snr_db, current_transcription |
| `attack_complete` | S→C | 收敛或达到 max_iter | success, final_transcription, resource URLs |
| `attack_error` | S→C | 异常中断 | error_code, message |

---

## Configuration

所有配置集中在 `backend/app/config.py`:

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `MODEL_NAME` | `facebook/wav2vec2-base-960h` | 靶机模型 |
| `SAMPLE_RATE` | 16000 | 音频采样率 |
| `NUM_SAMPLES` | 100 | 预加载样本数量 |
| `MIN_DURATION_SEC` | 3.0 | 最短音频时长 |
| `MAX_DURATION_SEC` | 5.0 | 最长音频时长 |
| `DEFAULT_EPSILON` | 0.01 | 扰动预算 |
| `DEFAULT_MAX_ITER` | 1000 | 最大迭代次数 |
| `DEFAULT_LAMBDA_L2` | 0.1 | L2 正则化权重 |
| `DEFAULT_LEARNING_RATE` | 5e-4 | Adam 学习率 |

---

## Research Context

本项目复现的核心论文：

> Carlini, N., & Wagner, D. (2018). *Audio Adversarial Examples: Targeted Attacks on Speech-to-Speech.*
> IEEE Security and Privacy Workshops.

**延伸阅读**:
- Baevski et al. (2020). *wav2vec 2.0: A Framework for Self-Supervised Learning of Speech Representations.* NeurIPS.
- Graves et al. (2006). *Connectionist Temporal Classification.* ICML.
- Mozilla Common Voice. https://commonvoice.mozilla.org/

---

## License

MIT — 仅供学术研究与教育用途。

---

## Build Verification

| Layer | Command | Result |
|-------|---------|--------|
| Backend | `python -m py_compile` (16 files) | ✅ 0 errors |
| Frontend | `npm run build` (vue-tsc + vite) | ✅ 0 errors, 654 modules, 5.9s |
