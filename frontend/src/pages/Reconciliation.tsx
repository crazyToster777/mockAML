import { useState } from 'react'
import { AlertCircle, CheckCircle2, Database, MessageSquare, RefreshCw } from 'lucide-react'
import { api, ReconciliationReport } from '../api/client'

function StatCard({ label, value, icon: Icon }: { label: string; value: number; icon: React.ElementType }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-center gap-4">
      <div className="p-2.5 rounded-lg bg-slate-100">
        <Icon size={18} className="text-slate-600" />
      </div>
      <div>
        <p className="text-slate-500 text-sm">{label}</p>
        <p className="font-display font-700 text-2xl text-slate-900 font-mono leading-tight">{value.toLocaleString()}</p>
      </div>
    </div>
  )
}

export default function Reconciliation() {
  const [report, setReport] = useState<ReconciliationReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function runReconciliation() {
    setLoading(true)
    setError(null)
    try {
      const result = await api.reconciliation()
      setReport(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display font-800 text-2xl text-slate-900">Reconciliation</h1>
          <p className="text-slate-500 text-sm mt-1">Compare Kafka messages against database records</p>
        </div>
        <button
          onClick={runReconciliation}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-700 transition-colors disabled:opacity-60"
        >
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          {loading ? 'Running...' : 'Run Reconciliation'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle size={18} className="text-red-500 shrink-0 mt-0.5" />
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {!report && !loading && !error && (
        <div className="bg-white rounded-xl border border-dashed border-slate-300 p-16 text-center">
          <p className="text-slate-400 text-sm">Click "Run Reconciliation" to check Kafka vs. database consistency</p>
        </div>
      )}

      {report && (
        <div className="space-y-6">
          <div className={`flex items-center gap-3 px-5 py-3 rounded-xl border ${report.is_healthy ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
            {report.is_healthy
              ? <CheckCircle2 size={20} className="text-green-600" />
              : <AlertCircle size={20} className="text-red-600" />}
            <p className={`font-medium text-sm ${report.is_healthy ? 'text-green-800' : 'text-red-800'}`}>
              {report.is_healthy ? 'Pipeline is healthy — all records reconcile' : 'Discrepancies detected — review below'}
            </p>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <StatCard label="Kafka Messages" value={report.kafka_total_messages} icon={MessageSquare} />
            <StatCard label="DB Transactions" value={report.db_transaction_count} icon={Database} />
            <StatCard label="DB Results" value={report.db_result_count} icon={Database} />
          </div>

          {(!report.is_healthy) && (
            <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
              <h2 className="font-display font-600 text-slate-800">Discrepancies</h2>
              <div className="space-y-2 text-sm">
                {report.missing_in_db > 0 && (
                  <div className="flex items-center justify-between px-4 py-2 bg-amber-50 rounded-lg border border-amber-200">
                    <span className="text-amber-800">Messages missing in DB</span>
                    <span className="font-mono font-bold text-amber-900">{report.missing_in_db}</span>
                  </div>
                )}
                {report.unverified_in_db > 0 && (
                  <div className="flex items-center justify-between px-4 py-2 bg-amber-50 rounded-lg border border-amber-200">
                    <span className="text-amber-800">Unverified records in DB</span>
                    <span className="font-mono font-bold text-amber-900">{report.unverified_in_db}</span>
                  </div>
                )}
                {report.duplicate_result_ids.length > 0 && (
                  <div className="px-4 py-2 bg-red-50 rounded-lg border border-red-200">
                    <p className="text-red-800 mb-1">Duplicate result IDs ({report.duplicate_result_ids.length})</p>
                    <p className="font-mono text-xs text-red-700 break-all">{report.duplicate_result_ids.join(', ')}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
