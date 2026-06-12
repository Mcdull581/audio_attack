import axios from 'axios'
import type {
  SampleListResponse,
  AttackConfigIn,
  AttackResponse,
  AttackStatusResponse,
} from '@/types/attack'

const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

export async function fetchSamples(): Promise<SampleListResponse> {
  const { data } = await apiClient.get<SampleListResponse>('/samples')
  return data
}

export async function startAttack(
  config: AttackConfigIn,
): Promise<AttackResponse> {
  const { data } = await apiClient.post<AttackResponse>('/attack/start', config)
  return data
}

export async function getAttackStatus(
  id: string,
): Promise<AttackStatusResponse> {
  const { data } = await apiClient.get<AttackStatusResponse>(
    `/attack/${id}/status`,
  )
  return data
}

export async function preloadSamples(): Promise<void> {
  await apiClient.post('/samples/preload')
}

export async function transcribeSample(name: string): Promise<string> {
  const { data } = await apiClient.get<{ transcription: string }>(
    `/samples/${encodeURIComponent(name)}/transcribe`,
  )
  return data.transcription
}
