/**
 * WebSocket message type definitions — must match backend WsEnvelope protocol
 * defined in backend/app/config.py exactly.
 */

// ── Message type discriminant ────────────────────────────────────────────

export type WsMessageType =
  | 'attack_started'
  | 'iteration_progress'
  | 'attack_complete'
  | 'attack_error';

// ── Base envelope ────────────────────────────────────────────────────────

export interface WsEnvelope {
  type: WsMessageType;
  attack_id: string;
}

// ── AttackStarted — sent when WS connection is established ───────────────

export interface AttackConfig {
  sample_name: string;
  target_phrase: string;
  epsilon: number;
  max_iterations: number;
  lambda_l2: number;
  learning_rate: number;
}

export interface AttackStartedMsg extends WsEnvelope {
  type: 'attack_started';
  config: AttackConfig;
  original_transcription: string;
  audio_duration_sec: number;
  push_interval: number;
}

// ── IterationProgress — pushed every push_interval iterations ────────────

export interface IterationProgressMsg extends WsEnvelope {
  type: 'iteration_progress';
  iteration: number;
  ctc_loss: number;
  l2_loss: number;
  total_loss: number;
  l2_norm_delta: number;
  snr_db: number;
  current_transcription: string;
  target_transcription: string;
  timestamp: number;
}

// ── AttackComplete — sent when attack converges or hits max_iter ─────────

export interface AttackResourceUrls {
  original_wav_url: string;
  adversarial_wav_url: string;
  perturbation_wav_url: string;
}

export interface AttackCompleteMsg extends WsEnvelope {
  type: 'attack_complete';
  total_iterations: number;
  final_ctc_loss: number;
  final_l2_norm: number;
  final_transcription: string;
  target_transcription: string;
  success: boolean;
  resources: AttackResourceUrls;
}

// ── AttackError — sent on unexpected failure ─────────────────────────────

export interface AttackErrorMsg extends WsEnvelope {
  type: 'attack_error';
  error_code: string;
  message: string;
  timestamp: number;
}

// ── Discriminated union ──────────────────────────────────────────────────

export type WsMessage =
  | AttackStartedMsg
  | IterationProgressMsg
  | AttackCompleteMsg
  | AttackErrorMsg;
