export interface Payment {
  transaction_id?: string
  customer_id: string
  timestamp: number
  amount: number
  merchant: string
  category: string
  merchant_lat: number
  merchant_lon: number
  home_lat?: number
  home_lon?: number
  device_id: string | null
  payment_method: string
}
export interface Customer { customer_id: string; home_lat: number; home_lon: number; device_id: string }
export interface Merchant { merchant: string; category: string; merchant_lat: number; merchant_lon: number }
export interface SparkovOptions {
  behavior_demo?: Payment | null
  customers: Customer[]; merchants: Merchant[]; case_count: number; examples: Payment[]
  metadata: { model_version: string; threshold: number; metrics: { test: { f1: number; precision: number; recall: number; average_precision: number } }; features: string[]; splits: { test: { min_timestamp: number; max_timestamp: number } } }
}
export interface EvidenceCase { case_id: string; amount: number; timestamp: number; known_at: number; summary: string; entity_matches: string[]; source: string }
export interface SparkovResult {
  recommendation: 'CLEAR' | 'FLAG' | 'ESCALATE'; risk_level: string; assessment_index: number
  evidence_confidence: string; confidence_basis: string[]; reasons: string[]; conflict_remaining: boolean
  risk: { risk_score: number; threshold: number; features: Record<string, string | number | null> }
  behavior: { history_status: string; history_count: number; recent_30d_count: number; findings: { code: string; detail: string }[]; baseline_mean_30d: number | null; time_profile?: { current_hour_utc: number; prior_90d_count: number; nearby_hour_count: number } }
  intelligence: { status: string; cases: EvidenceCase[]; limitations: string[]; merchant_prior_30d_volume?: number }
  plan: string[]; follow_up: Record<string, unknown> | null; quality: { limitations: string[]; meaning: string }
  explanation: string; explanation_mode: string; explanation_fallback_reason: string | null
}
export interface SparkovInvestigation {
  investigation_id: string; transaction_id: string; payment: Payment; status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  created_at: string; completed_stages: string[]; result: SparkovResult | null; error: string | null
  reviews: { review_id: string; reviewer: string; action: string; notes: string; created_at: string }[]
}
export type PaymentInput = Omit<Payment, 'timestamp' | 'transaction_id'> & { timestamp: string; currency: 'USD' }
