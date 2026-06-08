import { useState } from 'react'
import { AlertTriangle, CheckCircle2, Loader2, Send, Zap } from 'lucide-react'
import { api, TransactionType } from '../api/client'

const TX_TYPES: TransactionType[] = [
  'wire_transfer', 'ach', 'cash_deposit', 'cash_withdrawal', 'crypto_exchange',
]

const TX_LABELS: Record<TransactionType, string> = {
  wire_transfer:     'Wire Transfer',
  ach:               'ACH',
  cash_deposit:      'Cash Deposit',
  cash_withdrawal:   'Cash Withdrawal',
  crypto_exchange:   'Crypto Exchange',
}

type Status = { type: 'success' | 'error' | 'warn'; lines: string[] } | null

function Alert({ status }: { status: Status }) {
  if (!status) return null
  const styles = {
    success: 'bg-green-50 border-green-200 text-green-800',
    error:   'bg-red-50   border-red-200   text-red-800',
    warn:    'bg-amber-50 border-amber-200 text-amber-800',
  }
  const Icon = status.type === 'success' ? CheckCircle2 : AlertTriangle
  return (
    <div className={`flex items-start gap-3 px-4 py-3 rounded-lg border ${styles[status.type]}`}>
      <Icon size={16} className="shrink-0 mt-0.5" />
      <div className="text-sm space-y-0.5">
        {status.lines.map((l, i) => <p key={i}>{l}</p>)}
      </div>
    </div>
  )
}

export default function Produce() {
  const [tab, setTab] = useState<'bulk' | 'manual'>('bulk')

  // Bulk state
  const [count, setCount] = useState(10)
  const [includeSuspicious, setIncludeSuspicious] = useState(true)
  const [bulkLoading, setBulkLoading] = useState(false)
  const [bulkStatus, setBulkStatus] = useState<Status>(null)

  // Manual state
  const [accountId, setAccountId] = useState('ACCT100001')
  const [counterparty, setCounterparty] = useState('ACCT200001')
  const [amount, setAmount] = useState(500)
  const [txType, setTxType] = useState<TransactionType>('wire_transfer')
  const [manualLoading, setManualLoading] = useState(false)
  const [manualStatus, setManualStatus] = useState<Status>(null)

  async function handleBulk() {
    setBulkLoading(true)
    setBulkStatus(null)
    try {
      const res = await api.produceBulk({ count, include_suspicious: includeSuspicious })
      setBulkStatus({ type: 'success', lines: [`Produced ${res.produced} transactions to aml.transactions.`] })
    } catch (e: unknown) {
      setBulkStatus({ type: 'error', lines: [e instanceof Error ? e.message : 'Unknown error'] })
    } finally {
      setBulkLoading(false)
    }
  }

  async function handleManual(e: React.FormEvent) {
    e.preventDefault()
    setManualLoading(true)
    setManualStatus(null)
    try {
      const res = await api.produceSingle({
        account_id: accountId,
        counterparty_account_id: counterparty,
        amount_usd: amount,
        transaction_type: txType,
      })
      const lines = [`Transaction ${res.transaction_id.slice(0, 8)}… sent to Kafka.`, ...res.warnings]
      setManualStatus({ type: res.warnings.length > 0 ? 'warn' : 'success', lines })
    } catch (e: unknown) {
      setManualStatus({ type: 'error', lines: [e instanceof Error ? e.message : 'Unknown error'] })
    } finally {
      setManualLoading(false)
    }
  }

  return (
    <div className="p-8 space-y-6 max-w-2xl">
      <div>
        <h1 className="font-display font-800 text-2xl text-slate-900">Produce Transactions</h1>
        <p className="text-slate-500 text-sm mt-1">Send synthetic transactions to Kafka for AML pipeline testing</p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit">
        {(['bulk', 'manual'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
              tab === t ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}>
            {t === 'bulk' ? 'Bulk Generate' : 'Manual Transaction'}
          </button>
        ))}
      </div>

      {tab === 'bulk' && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-6">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-slate-700">Number of transactions</label>
              <span className="font-mono text-sm font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded">{count}</span>
            </div>
            <input type="range" min={1} max={100} value={count} onChange={e => setCount(Number(e.target.value))}
              className="w-full accent-blue-600" />
            <div className="flex justify-between text-xs text-slate-400 font-mono">
              <span>1</span><span>100</span>
            </div>
          </div>

          <label className="flex items-center gap-3 cursor-pointer">
            <input type="checkbox" checked={includeSuspicious} onChange={e => setIncludeSuspicious(e.target.checked)}
              className="rounded border-slate-300 text-blue-600 w-4 h-4" />
            <div>
              <p className="text-sm font-medium text-slate-700">Include suspicious transactions</p>
              <p className="text-xs text-slate-400">Injects a high-value and a blacklisted counterparty transaction</p>
            </div>
          </label>

          <Alert status={bulkStatus} />

          <button onClick={handleBulk} disabled={bulkLoading}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-60 w-full justify-center">
            {bulkLoading ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
            {bulkLoading ? `Producing ${count} transactions…` : `Produce ${count} transactions`}
          </button>
        </div>
      )}

      {tab === 'manual' && (
        <form onSubmit={handleManual} className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-slate-500 block mb-1.5">Account ID</label>
              <input value={accountId} onChange={e => setAccountId(e.target.value)} required minLength={6}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 block mb-1.5">Counterparty Account ID</label>
              <input value={counterparty} onChange={e => setCounterparty(e.target.value)} required minLength={6}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-slate-500 block mb-1.5">Amount (USD)</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">$</span>
                <input type="number" value={amount} min={0.01} step={0.01}
                  onChange={e => setAmount(Number(e.target.value))} required
                  className="w-full border border-slate-200 rounded-lg pl-7 pr-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 block mb-1.5">Transaction Type</label>
              <select value={txType} onChange={e => setTxType(e.target.value as TransactionType)}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
                {TX_TYPES.map(t => <option key={t} value={t}>{TX_LABELS[t]}</option>)}
              </select>
            </div>
          </div>

          {amount >= 10000 && (
            <p className="text-xs text-amber-600 bg-amber-50 px-3 py-2 rounded-lg border border-amber-200">
              Amount ≥ $10,000 — will trigger the <strong>amount_threshold</strong> rule.
            </p>
          )}
          {['SANCTIONED001', 'OFAC_BLOCKED_002', 'TERROR_FINANCE_003'].includes(counterparty.toUpperCase()) && (
            <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg border border-red-200">
              Counterparty is blacklisted — transaction will be <strong>BLOCKED</strong>.
            </p>
          )}

          <Alert status={manualStatus} />

          <button type="submit" disabled={manualLoading}
            className="flex items-center gap-2 px-5 py-2.5 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-700 transition-colors disabled:opacity-60 w-full justify-center">
            {manualLoading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            {manualLoading ? 'Sending…' : 'Send to Kafka'}
          </button>
        </form>
      )}
    </div>
  )
}
