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
│  │                 PGD Attack Engine                          │ │
│  │  ┌──────────────┐  ┌────────────┐  ┌────────────────────┐  │ │
│  │  │ Wav2Vec2     │  │ Momentum   │  │ CTC Loss + L2 Norm │  │ │
│  │  │ (frozen)     │  │ PGD +      │  │ δ ∈ [-ε, ε]       │  │ │
│  │  │              │  │ restarts   │  │ best checkpoint    │  │ │
│  │  └──────────────┘  └────────────┘  └────────────────────┘  │ │
│  │                                                             │ │
│  │  Data Pipeline: local sampled audio → manifest cache          │ │
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
| **Dataset** | `backend/data/sampled/` local audio | offline manifest scan |
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
│   │   │   ├── attack.py             # run_cw_attack_sync（PGD + 动量 + 重启）
│   │   │   ├── optimizer.py          # clamp + SNR 计算
│   │   │   ├── loader.py             # 本地音频扫描 → manifest
│   │   │   └── preprocess.py         # 重采样(16kHz)、能量裁剪、归一化
│   │   └── utils/
│   │       ├── audio_io.py           # torchaudio wav 读写
│   │       └── tensor_logger.py      # 张量序列化
│   ├── data/
│   │   └── sampled/                  # 本地音频文件（运行时扫描）
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

### 2. Backend Setup (Anaconda)

```bash
conda env create -f environment.yml
conda activate audio-attack
cd backend


# The model loader uses the local Hugging Face cache by default.
# Set AUDIO_ATTACK_LOCAL_ONLY=0 only when a model download is intended.
python -c "from app.engine.model import Wav2Vec2Wrapper; Wav2Vec2Wrapper()"

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 28000 --reload
```

### Data Source

项目使用 `backend/data/sampled/` 目录下的**本地音频文件**（支持 `.mp3`, `.wav`, `.flac`, `.ogg`）。启动时自动扫描该目录，通过 `soundfile` 读取元数据生成 `samples_manifest.json`。

**放置测试音频**：
```bash
# 将你的 Common Voice 音频文件放入此目录
cp /path/to/common_voice_*.mp3 backend/data/sampled/
# 强制重新扫描（保留已有转录）
curl -X POST http://localhost:28000/api/samples/preload
```

启动后服务会自动发现所有符合条件的音频文件（时长 1-15 秒），无需网络连接或 HuggingFace 下载。

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies /api and /ws to backend:28000)
npm run dev
```

The Vite dev server auto-proxies:
- `/api/*` → `http://localhost:28000`
- `/ws/*` → `ws://localhost:28000` (WebSocket)
- `/data/*` → `http://localhost:28000` (static wav files)

### 4. Docker (Optional)

```bash
cd backend

# Build the CUDA-enabled image
docker build -t audio-attack-lab .

# Run with GPU passthrough
docker run --gpus all -p 28000:28000 audio-attack-lab
```

---

## User Guide

以下逐步演示从零启动到完成一次完整攻击实验的全流程。

### Step 0 — 启动后端

```bash
cd backend
conda activate audio-attack
uvicorn app.main:app --host 0.0.0.0 --port 28000
```

终端输出关键日志：

```
Loading Wav2Vec2ForCTC facebook/wav2vec2-base-960h → cuda
Wav2Vec2Wrapper ready (params frozen, eval mode)
Scanning local audio files in backend/data/sampled …
[001/246] common_voice_en_1 (2.40 s)
...
Wrote manifest with 246 entries to backend/data/samples_manifest.json
```

> **首次启动说明**：默认只读取本地 Hugging Face 模型缓存，不会启动时反复联网；如果缓存不存在，请先设置 `AUDIO_ATTACK_LOCAL_ONLY=0` 后手动下载模型。样本目录启动时会快速扫描并生成 manifest。
>
> **Windows 用户**：若遇 `ModuleNotFoundError: No module named 'app'`，确认终端工作目录为 `backend/`，或使用：
> ```powershell
> cd C:\Users\Administrator\Desktop\token开发证明\audio_attack\backend
> $env:PYTHONPATH = "."
> uvicorn app.main:app --host 0.0.0.0 --port 28000
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
> - 页面空白 → 确认后端已启动在 28000 端口
> - 样本列表为空 → 点击 Sample List 顶部的 **"Preload Samples"** 按钮
> - 样式错乱 → 确认已执行 `npm install`

### Step 2 — 选择音频样本

在左侧 **Sample List** 面板中：

1. 等待样本列表加载（首次启动会自动 `GET /api/samples`）
2. 浏览本地样本列表，每条显示：
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
| **Epsilon (ε)** | 扰动强度上限（L∞ 范数） | `0.02` | 攻击不收敛 → 增大；扰动太明显（SNR 过低）→ 减小 |
| **Max Iterations / Restart** | 每次重启的 PGD 步数 | `1000` | 长目标可增加到 2000+ |
| **Lambda L2 (λ)** | L2 正则化权重 | `0.02` | 扰动幅度过大 → 增大；CTC Loss 降不下来 → 减小 |
| **Momentum** | 梯度动量系数 | `0.9` | 一般保持 0.8～0.95 |
| **Random Restarts** | 零初始化 + 随机初始化次数 | `3` | 提高跳出局部最优的概率 |

**参数调优经验**：
- 默认策略为定向 PGD + 动量 + 3 次重启，第一轮为零初始化，后续为随机初始化
- 每次更新后都投影回 `[-ε, ε]`，并保存当前最佳候选
- 一旦贪心解码与目标完全一致就提前停止
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
| 样本列表为空 | manifest 未生成或音频不在时长范围 | 点击 "Preload Samples"；检查 `backend/data/sampled/` 和后端日志 |
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
    config_dict={"epsilon": 0.02, "max_iterations": 1000, "lambda_l2": 0.02, "learning_rate": 1e-3, "momentum": 0.9, "restarts": 3, "attack_id": "cli"},
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

实现的是针对 CTC-based ASR 的白盒定向 PGD 攻击，借鉴 Carlini & Wagner (2018) 的目标函数：

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

**优化器**: Momentum PGD on δ, normalized gradient, step size = 1e-3
**多次重启**: 1 次零初始化 + 默认 2 次随机初始化
**约束投影**: 每步后 `clamp(δ, -ε, ε)`
**候选选择**: 优先精确匹配，其次字符编辑距离，最后 CTC Loss
**收敛判断**: `decode(argmax(logits)) == target_phrase`

---

## API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/samples` | 列出所有缓存的音频样本 |
| `POST` | `/api/samples/preload` | 强制重新扫描本地音频并更新 manifest（保留已有转录） |
| `GET` | `/api/samples/{name}/transcribe` | 模型推理获取音频真实转录 |
| `POST` | `/api/attack/start` | 创建 AttackJob（不立即执行） |
| `GET` | `/api/attack/{id}/status` | 查询攻击状态 |
| `POST` | `/api/attack/{id}/cancel` | 协作式取消运行中的攻击 |
| `GET` | `/api/audio/download/{type}/{filename}` | 下载 wav（original/adversarial/delta）|

### WebSocket Protocol

| Message Type | Direction | Trigger | Payload |
|-------------|-----------|---------|---------|
| `attack_started` | S→C | WS 连接建立 | config, original_transcription, audio_duration_sec |
| `iteration_progress` | S→C | 按全局预算推送 | iteration, restart_index, ctc_loss, l2_loss, snr_db, current_transcription |
| `attack_complete` | S→C | 收敛或达到 max_iter | success, final_transcription, resource URLs |
| `attack_error` | S→C | 异常中断 | error_code, message |

---

## Configuration

所有配置集中在 `backend/app/config.py`:

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `MODEL_NAME` | `facebook/wav2vec2-base-960h` | 靶机模型 |
| `SAMPLE_RATE` | 16000 | 音频采样率 |
| `NUM_SAMPLES` | — | 兼容保留；本地扫描器不再截断样本 |
| `MIN_DURATION_SEC` | 1.0 | 最短音频时长 |
| `MAX_DURATION_SEC` | 15.0 | 最长音频时长 |
| `DEFAULT_EPSILON` | 0.02 | 扰动预算 |
| `DEFAULT_MAX_ITER` | 1000 | 最大迭代次数 |
| `DEFAULT_LAMBDA_L2` | 0.02 | L2 正则化权重 |
| `DEFAULT_LEARNING_RATE` | 1e-3 | PGD 步长 |
| `DEFAULT_MOMENTUM` | 0.9 | 动量系数 |
| `DEFAULT_RESTARTS` | 3 | 初始化次数 |

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

## Key Features

| Feature | Detail |
|---------|--------|
| **优雅取消** | WebSocket 断开 → `threading.Event` 信号立即终止攻击循环，释放 GPU/CPU |
| **显存清理** | 每次攻击结束后 `gc.collect()` + `torch.cuda.empty_cache()` 防止多次攻击累积 |
| **本地音频** | 扫描 `backend/data/sampled/` 目录中的 `.mp3/.wav/.flac`，无需网络下载 |
| **自动重采样** | `soundfile` + `torchaudio` 将所有音频自动转为 16kHz 单声道 |
| **Ground Truth 转录** | 选中样本时自动调用模型推理获取真实文本标签，显示在波形信息栏 |
| **双轨频谱图** | wavesurfer.js Spectrogram 插件 — 原始 vs 对抗频谱上下对比，高频噪点肉眼可见 |
| **Sync Scale 开关** | 对抗波形旁一键切换 `normalize`，直观对比扰动幅度 |
| **实时转录大屏** | `TranscriptionHero` — 大字等宽字体实时显示识别收敛过程，SNR 颜色徽章 |

---

## Build Verification

| Layer | Command | Result |
|-------|---------|--------|
| Backend | `python -m py_compile` (16 files) | ✅ 0 errors |
| Frontend | `npm run build` (vue-tsc + vite) | ✅ 0 errors |

---

## License

MIT — 仅供学术研究与教育用途。

---
