import type { PaymentInput, SparkovInvestigation, SparkovOptions } from '../sparkovTypes'

const base = (import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? '/api' : '')).replace(/\/$/, '')
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(`${base}/v2${path}`, { ...init, signal: AbortSignal.timeout(45000) }) }
  catch { throw new Error('The workspace could not be reached. Please check the local service and try again.') }
  if (!response.ok) {
    if (response.status === 405 && init?.method === 'DELETE') {
      throw new Error('Nothing was deleted. The local service needs to be restarted to enable deletion. Restart the backend, then try again.')
    }
    const body = await response.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail.map((item: { msg: string }) => item.msg).join('; ') : `Request failed (${response.status})`
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}
const post = (body: unknown) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
export const sparkovApi = {
  options: () => request<SparkovOptions>('/options'),
  investigations: () => request<SparkovInvestigation[]>('/investigations?limit=100'),
  get: (id: string) => request<SparkovInvestigation>(`/investigations/${encodeURIComponent(id)}`),
  delete: (id: string) => request<{ transaction_id: string; deleted_case_ids: string[] }>(`/investigations/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  start: (payment: PaymentInput) => request<{ investigation_id: string }>('/investigate', post(payment)),
  review: (id: string, body: { reviewer: string; action: string; notes: string }) => request<SparkovInvestigation>(`/investigations/${encodeURIComponent(id)}/review`, post(body)),
}
