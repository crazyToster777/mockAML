const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `${res.status}`)
  }
  return res.json()
}

export interface OverviewStats {
  total_transactions: number
  verified: number
  suspicious: number
  detection_rate: number
}

export interface RecentAlert {
  transaction_id: string
  account_id: string
  risk_level: string
  amount_usd: number
  triggered_rules: string[]
  notes: string
  verified_at: string
}

export interface TransactionRow {
  result_id: string
  transaction_id: string
  account_id: string
  risk_level: string
  amount_usd: number
  triggered_rules: string[]
  notes: string
  verified_at: string
}

export interface TransactionsPage {
  items: TransactionRow[]
  total: number
}

export interface RiskCount    { risk_level: string; count: number }
export interface VolumePoint  { hour: string; low: number; medium: number; high: number; blocked: number }
export interface RuleCount    { rule: string; count: number }
export interface CumulativePoint { verified_at: string; cumulative: number }

export type TransactionType =
  | 'wire_transfer' | 'ach' | 'cash_deposit' | 'cash_withdrawal' | 'crypto_exchange'

export interface BulkRequest   { count: number; include_suspicious: boolean }
export interface BulkResponse  { produced: number }
export interface SingleRequest {
  account_id: string
  counterparty_account_id: string
  amount_usd: number
  transaction_type: TransactionType
}
export interface SingleResponse { transaction_id: string; warnings: string[] }

export interface ReconciliationReport {
  is_healthy: boolean
  kafka_total_messages: number
  db_transaction_count: number
  db_result_count: number
  missing_in_db: number
  unverified_in_db: number
  duplicate_result_ids: string[]
}

export const api = {
  overviewStats:          () => get<OverviewStats>('/overview/stats'),
  recentAlerts:           (limit = 10) => get<RecentAlert[]>(`/overview/recent-alerts?limit=${limit}`),
  transactions:           (params: Record<string, string>) =>
    get<TransactionsPage>('/transactions?' + new URLSearchParams(params)),
  riskDistribution:       () => get<RiskCount[]>('/analytics/risk-distribution'),
  volumeOverTime:         () => get<VolumePoint[]>('/analytics/volume-over-time'),
  triggeredRules:         () => get<RuleCount[]>('/analytics/triggered-rules'),
  cumulativeSuspicious:   () => get<CumulativePoint[]>('/analytics/cumulative-suspicious'),
  reconciliation:         () => get<ReconciliationReport>('/reconciliation'),
  produceBulk:   (body: BulkRequest)   => post<BulkResponse>('/produce/bulk', body),
  produceSingle: (body: SingleRequest) => post<SingleResponse>('/produce/single', body),
}
