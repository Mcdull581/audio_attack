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

### Data Source

项目使用 `backend/data/sampled/` 目录下的**本地音频文件**（支持 `.mp3`, `.wav`, `.flac`, `.ogg`）。启动时自动扫描该目录，通过 `soundfile` 读取元数据生成 `samples_manifest.json`。

**放置测试音频**：
```bash
# 将你的 Common Voice 音频文件放入此目录
cp /path/to/common_voice_*.mp3 backend/data/sampled/
# 删除旧 manifest 以触发重新扫描
rm backend/data/samples_manifest.json
```

启动后服务会自动发现所有符合条件的音频文件（时长 1-15 秒），无需网络连接或 HuggingFace 下载。

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

## User Guide

以下逐步演示从零启动到完成一次完整攻击实验的全流程。

### Step 0 — 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

终端输出关键日志：

```
Loading Wav2Vec2ForCTC facebook/wav2vec2-base-960h → cuda
Wav2Vec2Wrapper ready (params frozen, eval mode)
Streaming mozilla-foundation/common_voice_25_0/en (split=test) …
[001/100] cv_en_00001 (3.45 s) the quick brown fox jumps over the lazy dog
...
Wrote manifest with 100 entries to backend/data/samples_manifest.json
```

> **首次启动说明**：模型下载约 360 MB，数据集流式抽取约 1-3 分钟。后续启动跳过下载，直接加载 manifest 缓存。
>
> **Windows 用户**：若遇 `ModuleNotFoundError: No module named 'app'`，确认终端工作目录为 `backend/`，或使用：
> ```powershell
> cd C:\Users\Administrator\Desktop\audio_attack\backend
> $env:PYTHONPATH = "."
> uvicorn app.main:app --host 0.0.0.0 --port 8000
> ```

### Step 1 — 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`。页面结构：

```
┌──────────────────────────────────────────────────────────────┐
│  ⚡ Audio Attack Lab                                         │
├──────────────┬───────────────────────────────────────────────┤
│              │                                               │
│  [Sidebar]   │         [Visualization Area]                  │
│              │                                               │
│  Sample      │  ┌─────────────────────────────────────────┐  │
│  List        │  │         Waveform Comparison             │  │
│  (click to   │  │  Original ─────────────────────────     │  │
│   select)    │  │  Adversarial ───────────────────────     │  │
│              │  └─────────────────────────────────────────┘  │
│  Attack      │                                               │
│  Panel       │  ┌─────────────────────────────────────────┐  │
│  (configure) │  │         Loss Curve (ECharts)            │  │
│              │  │  CTC Loss ────  L2 Norm ────  SNR ──    │  │
│              │  └─────────────────────────────────────────┘  │
│              │                                               │
│              │  ┌─────────────────────────────────────────┐  │
│              │  │      Spectrogram Comparison             │  │
│              │  └─────────────────────────────────────────┘  │
├──────────────┴───────────────────────────────────────────────┤
│  ● Idle  │ Iter: --/--  │ SNR: -- dB  │ Ready — configure   │
└──────────────────────────────────────────────────────────────┘
```

> **常见问题**：
> - 页面空白 → 确认后端已启动在 8000 端口
> - 样本列表为空 → 点击 Sample List 顶部的 **"Preload Samples"** 按钮
> - 样式错乱 → 确认已执行 `npm install`

### Step 2 — 选择音频样本

在左侧 **Sample List** 面板中：

1. 等待样本列表加载（首次启动会自动 `GET /api/samples`）
2. 浏览 100 条语音，每条显示：
   - 样本名（如 `cv_en_00042`）
   - 转录文本预览（如 "the weather forecast..."）
   - 时长标签（如 `0:03` = 3 秒）
3. **点击** 任意条目选中该样本
   - 选中态：左侧青色边框高亮
   - 点击 ▶ 按钮可试听（需要后端音频服务就绪）
4. Attack Panel 中 "Audio Sample" 区域**同步显示**已选样本名及时长

### Step 3 — 配置攻击参数

在 **Attack Panel** 中设置：

| 参数 | 说明 | 推荐值 | 何时调整 |
|------|------|--------|---------|
| **Target Phrase** | 想让模型"听成"的文本 | `hello world` | 每次实验必填 |
| **Epsilon (ε)** | 扰动强度上限（L∞ 范数） | `0.01` | 攻击不收敛 → 增大至 0.02；扰动太明显（SNR 过低）→ 减小至 0.005 |
| **Max Iterations** | 最大优化步数 | `1000` | 500 步足够短文本收敛；长短语需要 2000+ |
| **Lambda L2 (λ)** | L2 正则化权重 | `0.1` | 扰动幅度过大 → 增大 λ；CTC Loss 降不下来 → 减小 λ |

**参数调优经验**：
- ε = 0.01, λ = 0.1 是论文的默认组合，适用于大多数 3-5 秒语音
- 攻击失败时优先增加 max_iterations，其次增大 ε
- SNR < 10 dB 时人耳可察觉扰动，建议 SNR > 20 dB

### Step 4 — 启动攻击

点击 **"Start Attack"** 按钮后：

1. **前端**：POST `/api/attack/start` → 获得 `attack_id`
2. **前端**：打开 WebSocket 连接到 `/ws/attack/{attack_id}`
3. **后端**：启动攻击线程，PyTorch 开始在 GPU 上反向传播
4. **UI 行为**：
   - Attack Panel 锁定（参数不可修改，防重复提交 / OOM）
   - 按钮变为旋转加载动画 + "Attack Running..."
   - StatusBar 状态指示灯变为绿色

### Step 5 — 实时监控

攻击运行期间，右侧面板实时更新：

**Loss Curve（ECharts）**：
- 蓝色实线 → CTC Loss（应持续下降）
- 橙色实线 → L2 Norm（波动，取决于 λ）
- 绿色虚线 → SNR（越高越好，表示扰动越小）
- 悬停数据点查看精确数值

**Status Bar（底部）**：
- 状态指示灯：🟢 Running
- 当前迭代 / 总迭代数
- 实时 SNR 值
- **转录收敛动画**：当前识别文本 → 目标文本（打字机效果）

**典型收敛过程**：

```
Iter 100:  "hhhelllo wwwworrld"  →  "hello world"   (ctc=45.2, l2=0.03)
Iter 300:  "helo world"          →  "hello world"   (ctc=12.1, l2=0.08)
Iter 500:  "hello world"         →  "hello world"   (ctc=0.23, l2=0.12) ← 收敛！
```

### Step 6 — 分析结果

攻击完成后，UI 自动解锁并展示结果：

**成功场景**（转录完全匹配）：
- 绿色横幅："Attack succeeded!"
- "Download Results" 按钮可导出对抗样本 wav
- Loss 曲线在低 CTC Loss 处平稳

**未收敛场景**（转录不完全匹配）：
- 红色横幅：显示最终转录 vs 目标文本
- 建议：增加 max_iterations 或调整 ε/λ 后重新攻击

**波形对比**（WaveformView）：
- 上方：原始音频波形（青色）
- 下方：对抗音频波形（红色）
- 点 ▶ 按钮同步播放原声与对抗声，**人耳难以分辨差异**（成功攻击的关键指标）

**结果文件**（可下载）：

| 文件 | 路径 | 说明 |
|------|------|------|
| 原始音频 | `/api/audio/download/original/{id}.wav` | 未修改的输入 |
| 对抗音频 | `/api/audio/download/adversarial/{id}.wav` | 添加扰动后的输出 |
| 扰动信号 | `/api/audio/download/delta/{id}.wav` | δ = 对抗 - 原始（放大后可听见差分）|

### 调试技巧

**常见问题排查**：

| 症状 | 可能原因 | 解决方案 |
|------|---------|---------|
| 样本列表为空 | manifest 未生成 | 点击 "Preload Samples"；检查后端日志是否有 HF 网络错误 |
| "Start Attack" 灰色不可点击 | 未选择样本或未输入目标短语 | 先点击 Sample List 中的条目，填写 Target Phrase |
| 攻击启动后立即 "Failed" | GPU OOM 或 CUDA 错误 | 检查 `nvidia-smi`；关闭其他 GPU 进程；重启后端 |
| CTC Loss 不下降 | 学习率不合适或目标短语无意义 | 尝试 `lr=1e-3`；确保目标短语由常见英文单词组成 |
| WebSocket 频繁断开 | 后端计算阻塞事件循环 | 重启后端：已使用 `asyncio.to_thread` 隔离，正常不应出现 |

### 快速实验脚本

如果想跳过 UI，直接用命令行启动攻击：

```python
# run_attack.py — 放在 backend/ 目录下
import torch
from app.engine.model import Wav2Vec2Wrapper
from app.engine.attack import run_cw_attack_sync
from app.utils.audio_io import load_wav, save_wav

wrapper = Wav2Vec2Wrapper()
waveform, sr = load_wav("data/sampled/cv_en_00001.wav")

# 进度回调（打印到终端）
def progress_cb(msg):
    if msg["type"] == "iteration_progress":
        print(f"[{msg['iteration']:4d}] ctc={msg['ctc_loss']:.3f} l2={msg['l2_loss']:.4f} text={msg['current_transcription']!r}")

adv, delta, results = run_cw_attack_sync(
    waveform=waveform,
    sample_rate=sr,
    target_phrase="hello world",
    wrapper=wrapper,
    config_dict={"epsilon": 0.01, "max_iterations": 500, "lambda_l2": 0.1, "learning_rate": 5e-4, "attack_id": "cli"},
    progress_callback=progress_cb,
)

print(f"\nSuccess: {results['success']}")
print(f"Final transcription: {results['final_transcription']!r}")
save_wav("adversarial.wav", adv, sr)
save_wav("perturbation.wav", delta, sr)
```

```bash
python run_attack.py
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