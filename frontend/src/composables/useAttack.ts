/**
 * useAttack — Attack lifecycle state machine.
 *
 * Orchestrates the full attack flow:
 *   1. POST /api/attack/start with config
 *   2. Store attackId in Pinia
 *   3. Open WebSocket for real-time progress
 *   4. Expose idle / running / complete derived state
 *
 * All API calls use fetch() directly to avoid extra dependency weight.
 */

import { computed, ref, type Ref, type ComputedRef } from 'vue';
import { useAttackStore } from '@/stores/attackStore';
import { useAudioStore } from '@/stores/audioStore';
import { useWebSocket } from '@/composables/useWebSocket';
import type { AttackConfigIn, AttackResponse } from '@/types/attack';
import type { AttackStatus } from '@/types/attack';

// ── Helpers ──────────────────────────────────────────────────────────────

interface StartAttackParams {
  sampleName: string;
  targetPhrase: string;
  epsilon?: number;
  maxIterations?: number;
  lambdaL2?: number;
}

function buildConfig(params: StartAttackParams): AttackConfigIn {
  return {
    sample_name: params.sampleName,
    target_phrase: params.targetPhrase,
    epsilon: params.epsilon ?? 0.01,
    max_iterations: params.maxIterations ?? 1000,
    lambda_l2: params.lambdaL2 ?? 0.1,
    learning_rate: 5e-4,
  };
}

// ── Composable ───────────────────────────────────────────────────────────

export function useAttack() {
  const attackStore = useAttackStore();
  const audioStore = useAudioStore();

  const attackIdRef = ref<string | null>(null);

  const ws = useWebSocket(attackIdRef);

  // ── Derived state ──────────────────────────────────────────────────────

  const attackId: ComputedRef<string | null> = computed(
    () => attackStore.attackId,
  );

  const isIdle: ComputedRef<boolean> = computed(
    () =>
      attackStore.status === 'queued' ||
      attackStore.status === 'cancelled',
  );

  const isRunning: ComputedRef<boolean> = computed(
    () => attackStore.isRunning,
  );

  const isComplete: ComputedRef<boolean> = computed(
    () => attackStore.isComplete,
  );

  // ── Actions ────────────────────────────────────────────────────────────

  async function startAttack(
    sampleName: string,
    targetPhrase: string,
    epsilon?: number,
    maxIterations?: number,
    lambdaL2?: number,
  ): Promise<string> {
    // Prevent double-start
    if (attackStore.isRunning) {
      throw new Error('An attack is already running');
    }

    const config = buildConfig({
      sampleName,
      targetPhrase,
      epsilon,
      maxIterations,
      lambdaL2,
    });

    // Reset stores for a clean slate
    attackStore.reset();
    audioStore.reset();
    ws.disconnect();

    // Submit attack config to backend
    const response = await fetch('/api/attack/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      const detail =
        (errBody as { detail?: string }).detail ??
        `HTTP ${response.status}`;
      throw new Error(`Failed to start attack: ${detail}`);
    }

    const body: AttackResponse = await response.json();

    // Wire into store
    attackStore.attackId = body.attack_id;
    attackStore.status = body.status;
    attackStore.config = body.config;
    attackIdRef.value = body.attack_id;

    // Open real-time WS feed
    ws.connect();

    return body.attack_id;
  }

  async function abortAttack(): Promise<void> {
    const id = attackId.value;
    if (!id) return;

    try {
      await fetch(`/api/attack/${id}/cancel`, { method: 'POST' });
    } catch {
      // Best-effort; the WS will eventually close if the backend aborts
      console.warn('[useAttack] Cancel request failed for attack', id);
    }

    ws.disconnect();
    attackStore.reset();
    audioStore.reset();
    attackIdRef.value = null;
  }

  // ── Public API ─────────────────────────────────────────────────────────

  return {
    // state
    attackId,
    isIdle,
    isRunning,
    isComplete,
    // actions
    startAttack,
    abortAttack,
  };
}
