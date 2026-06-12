/**
 * Pinia store for attack lifecycle state.
 * Receives real-time updates from useWebSocket and exposes derived progress.
 *
 * Uses Composition API style (setup function) per Pinia best practices.
 */

import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import type {
  AttackConfigIn,
  AttackStatus,
  LossDataPoint,
} from '@/types/attack';
import type {
  WsMessage,
  AttackStartedMsg,
  IterationProgressMsg,
  AttackCompleteMsg,
  AttackErrorMsg,
} from '@/types/ws';

// ── Constants ────────────────────────────────────────────────────────────

const MAX_LOSS_HISTORY = 500;

// ── Store ────────────────────────────────────────────────────────────────

export const useAttackStore = defineStore('attack', () => {
  // ── State ──────────────────────────────────────────────────────────────

  const attackId = ref<string | null>(null);
  const status = ref<AttackStatus>('idle');
  const config = ref<AttackConfigIn | null>(null);
  const currentIteration = ref(0);
  const ctcLoss = ref(0);
  const l2Loss = ref(0);
  const snrDb = ref(0);
  const currentTranscription = ref('');
  const targetTranscription = ref('');
  const lossHistory = ref<LossDataPoint[]>([]);
  const error = ref<string | null>(null);

  // ── Getters ────────────────────────────────────────────────────────────

  const isRunning = computed(() => status.value === 'running');

  const isComplete = computed(() => status.value === 'completed');

  const isFailed = computed(() => status.value === 'failed');

  const progressPercent = computed(() => {
    if (!config.value || config.value.max_iterations <= 0) return 0;
    return Math.min(
      100,
      (currentIteration.value / config.value.max_iterations) * 100,
    );
  });

  // ── Message handlers ───────────────────────────────────────────────────

  function handleAttackStarted(msg: AttackStartedMsg): void {
    config.value = msg.config;
    status.value = 'running';
    targetTranscription.value = msg.config.target_phrase;
    currentTranscription.value = msg.original_transcription;
    currentIteration.value = 0;
    error.value = null;
  }

  function handleIterationProgress(msg: IterationProgressMsg): void {
    currentIteration.value = msg.iteration;
    ctcLoss.value = msg.ctc_loss;
    l2Loss.value = msg.l2_loss;
    snrDb.value = msg.snr_db;
    currentTranscription.value = msg.current_transcription;

    addLossPoint({
      iteration: msg.iteration,
      ctc_loss: msg.ctc_loss,
      l2_loss: msg.l2_loss,
      total_loss: msg.total_loss,
      snr_db: msg.snr_db,
      timestamp: msg.timestamp,
    });
  }

  function handleAttackComplete(msg: AttackCompleteMsg): void {
    status.value = 'completed';
    currentIteration.value = msg.total_iterations;
    ctcLoss.value = msg.final_ctc_loss;
    currentTranscription.value = msg.final_transcription;
    targetTranscription.value = msg.target_transcription;
  }

  function handleAttackError(msg: AttackErrorMsg): void {
    status.value = 'failed';
    error.value = msg.message;
  }

  // ── Actions ────────────────────────────────────────────────────────────

  function handleWsMessage(msg: WsMessage): void {
    switch (msg.type) {
      case 'attack_started':
        handleAttackStarted(msg);
        break;
      case 'iteration_progress':
        handleIterationProgress(msg);
        break;
      case 'attack_complete':
        handleAttackComplete(msg);
        break;
      case 'attack_error':
        handleAttackError(msg);
        break;
      default: {
        const _exhaustive: never = msg;
        void _exhaustive;
        break;
      }
    }
  }

  function addLossPoint(point: LossDataPoint): void {
    const history = lossHistory.value;
    history.push(point);
    // Cap history size to avoid unbounded memory growth
    if (history.length > MAX_LOSS_HISTORY) {
      lossHistory.value = history.slice(history.length - MAX_LOSS_HISTORY);
    }
  }

  function reset(): void {
    attackId.value = null;
    status.value = 'idle';
    config.value = null;
    currentIteration.value = 0;
    ctcLoss.value = 0;
    l2Loss.value = 0;
    snrDb.value = 0;
    currentTranscription.value = '';
    targetTranscription.value = '';
    lossHistory.value = [];
    error.value = null;
  }

  // ── Public API ─────────────────────────────────────────────────────────

  return {
    // state
    attackId,
    status,
    config,
    currentIteration,
    ctcLoss,
    l2Loss,
    snrDb,
    currentTranscription,
    targetTranscription,
    lossHistory,
    error,
    // getters
    isRunning,
    isComplete,
    isFailed,
    progressPercent,
    // actions
    handleWsMessage,
    addLossPoint,
    reset,
  };
});
