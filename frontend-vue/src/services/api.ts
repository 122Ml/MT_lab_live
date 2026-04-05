import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  timeout: 60000
})

export type EngineName = 'rbmt' | 'smt' | 'nmt' | 'transformer' | 'llm_api'

export interface TranslatePayload {
  text: string
  src_lang: string
  tgt_lang: string
  engines: EngineName[]
  reference?: string
}

export interface BatchTranslatePayload {
  texts: string[]
  src_lang: string
  tgt_lang: string
  engines: EngineName[]
  references?: string[]
}

export interface EngineResult {
  engine: EngineName
  translation: string
  latency_ms: number
  ready: boolean
  error?: string
  bleu?: number
  chrf?: number
}

export interface TranslateResponse {
  text: string
  src_lang: string
  tgt_lang: string
  reference?: string
  results: EngineResult[]
}

export interface BatchTranslateResponse {
  items: TranslateResponse[]
}

export interface TestCase {
  id: string
  source: string
  reference: string
  src_lang: string
  tgt_lang: string
}

export async function translate(payload: TranslatePayload) {
  const { data } = await api.post<TranslateResponse>('/api/v1/translate', payload)
  return data
}

export async function batchTranslate(payload: BatchTranslatePayload) {
  const { data } = await api.post<BatchTranslateResponse>('/api/v1/batch_translate', payload)
  return data
}

export async function getEngines() {
  const { data } = await api.get('/api/v1/engines')
  return data as Record<string, { ready: boolean; message: string }>
}

export async function getTestCases() {
  const { data } = await api.get<TestCase[]>('/api/v1/test_cases')
  return data
}
