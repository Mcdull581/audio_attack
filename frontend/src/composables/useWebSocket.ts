/**
 * useWebSocket — WebSocket connection manager with auto-reconnect.
 *
 * Opens a persistent WS connection to /ws/attack/{attackId}, dispatches
 * typed messages to the attackStore, and pushes resource URLs to the
 * audioStore on completion. Handles exponential-backoff reconnection
 * capped at 5 retries.
 */

import { ref, onUnmounted, type Ref, type ShallowRef, shallowRef } from 'vue';
import { useAttackStore } from '@/stores/attackStore';
import { useAudioStore } from '@/stores/audioStore';
import type { WsMessage, WsMessageType } from '@/types/ws';

// ── Reconnect policy ─────────────────────────────────────────────────────

const MAX_RETRIES = 5;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30_000;

// ── Known WS message types for validation ────────────────────────────────

const VALID_TYPES: ReadonlySet<string> = new Set<WsMessageType>([
  'attack_started',
  'iteration_progress',
  'attack_complete',
  'attack_error',
]);

// ── Helpers ──────────────────────────────────────────────────────────────

function buildWsUrl(attackId: string): string {
  const host =
    typeof location !== 'undefined'
      ? `${location.host}/ws/attack/${attackId}`
      : `localhost:8000/ws/attack/${attackId}`;
  const protocol = location?.protocol === 'https:' ? 'wss' : 'ws';
  if (import.meta.env.DEV) {
    // In dev, connect directly to the backend port (bypasses Vite proxy)
    return `ws://localhost:8000/ws/attack/${attackId}`;
  }
  return `${protocol}://${host}`;
}

function isValidMessage(raw: unknown): raw is WsMessage {
  if (typeof raw !== 'object' || raw === null) return false;
  const obj = raw as Record<string, unknown>;
  return (
    typeof obj.type === 'string' &&
    VALID_TYPES.has(obj.type) &&
    typeof obj.attack_id === 'string'
  );
}

// ── Terminal message types (stop reconnection) ───────────────────────────

const TERMINAL_TYPES: ReadonlySet<string> = new Set([
  'attack_complete',
  'attack_error',
]);

// ── Composable ───────────────────────────────────────────────────────────

export function useWebSocket(attackId: Ref<string | null> | string) {
  const isConnected = ref(false);
  const lastMessage: ShallowRef<WsMessage | null> = shallowRef(null);

  let socket: WebSocket | null = null;
  let retryCount = 0;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let manualDisconnect = false;

  const attackStore = useAttackStore();
  const audioStore = useAudioStore();

  // ── Cleanup ────────────────────────────────────────────────────────────

  function clearRetryTimer(): void {
    if (retryTimer !== null) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
  }

  function closeSocket(): void {
    if (socket !== null) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      socket.onerror = null;
      socket.close();
      socket = null;
    }
  }

  // ── Message handler ────────────────────────────────────────────────────

  function handleMessage(event: MessageEvent): void {
    let raw: unknown;
    try {
      raw = JSON.parse(event.data as string);
    } catch {
      console.warn('[useWebSocket] Failed to parse WS message as JSON');
      return;
    }

    if (!isValidMessage(raw)) {
      console.warn('[useWebSocket] Invalid WS message shape', raw);
      return;
    }

    lastMessage.value = raw;
    attackStore.handleWsMessage(raw);

    // On completion: stop retries, push resource URLs to audio store
    if (raw.type === 'attack_complete') {
      audioStore.setResources(raw.resources);
    }
  }

  // ── Reconnect logic ────────────────────────────────────────────────────

  function scheduleReconnect(): void {
    if (manualDisconnect || retryCount >= MAX_RETRIES) return;

    const delay = Math.min(BASE_DELAY_MS * 2 ** retryCount, MAX_DELAY_MS);
    retryTimer = setTimeout(() => {
      retryTimer = null;
      retryCount++;
      connect();
    }, delay);
  }

  // ── Connection ─────────────────────────────────────────────────────────

  function connect(): void {
    // Resolve attackId whether passed as Ref or raw string
    const id = typeof attackId === 'string' ? attackId : attackId.value;
    if (!id) return;

    // Prevent double-connect
    if (socket && socket.readyState === WebSocket.OPEN) return;

    const url = buildWsUrl(id);

    try {
      socket = new WebSocket(url);
    } catch {
      console.warn('[useWebSocket] Failed to construct WebSocket for', url);
      scheduleReconnect();
      return;
    }

    socket.onopen = () => {
      isConnected.value = true;
      retryCount = 0; // reset backoff on successful connection
    };

    socket.onmessage = handleMessage;

    socket.onclose = (event) => {
      isConnected.value = false;

      if (manualDisconnect) return;

      // If the server sent a terminal message, don't retry
      const last = lastMessage.value;
      if (last && TERMINAL_TYPES.has(last.type)) return;

      // Abnormal closure (not clean server-initiated close)
      if (event.code !== 1000) {
        scheduleReconnect();
      }
    };

    socket.onerror = () => {
      // onclose will fire after onerror; reconnect is handled there
    };
  }

  function disconnect(): void {
    manualDisconnect = true;
    clearRetryTimer();
    closeSocket();
    isConnected.value = false;
    retryCount = 0;
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────

  onUnmounted(() => {
    disconnect();
  });

  // ── Public API ─────────────────────────────────────────────────────────

  return {
    isConnected,
    lastMessage,
    connect,
    disconnect,
  };
}
