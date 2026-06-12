/**
 * Attack configuration, response, and sample types.
 * Mirrors the Pydantic models in backend/app/config.py.
 */

// ── Attack config (sent from frontend via POST /api/attack/start) ────────

export interface AttackConfigIn {
  sample_name: string;
  target_phrase: string;
  epsilon: number;
  max_iterations: number;
  lambda_l2: number;
  learning_rate: number;
}

// ── Attack status lifecycle ──────────────────────────────────────────────

export type AttackStatus =
  | 'idle'
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

// ── REST response types ──────────────────────────────────────────────────

export interface AttackResponse {
  attack_id: string;
  status: AttackStatus;
  config: AttackConfigIn;
}

export interface SampleInfo {
  id: string;
  name: string;
  local_path: string;
  duration_sec: number;
  duration: number;
  format: string;
  transcription: string;
}

export interface SampleListResponse {
  samples: SampleInfo[];
  total: number;
}

export interface AttackStatusResponse {
  attack_id: string;
  status: AttackStatus;
  progress: number;
  result?: Record<string, unknown>;
  error?: string;
}

// ── Loss history data point (accumulated client-side) ────────────────────

export interface LossDataPoint {
  iteration: number;
  ctc_loss: number;
  l2_loss: number;
  total_loss: number;
  snr_db: number;
  timestamp: number;
}
