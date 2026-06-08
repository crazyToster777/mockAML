import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle, TrendingUp, Zap } from 'lucide-react'
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge'

const RISK_COLORS: Record<string, string> = {
  low: '#22c55e', medium: '#f59e0b', high: '#ef4444', blocked: '#7c3aed',
}

function StatCard({ label, value, sub, icon: Icon, accent }: {
  label: string; value: string | number; sub?: string; icon: React.ElementType; accent: string
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-start gap-4">
      <div className={`p-2.5 rounded-lg ${accent}`}>
        <Icon size={18} className="text-white" />
      </div>
      <div>
        <p className="text-slate-500 text-sm">{label}</p>
        <p className="font-display font-700 text-2xl text-slate-900 leading-tight">{value}</p>
        {sub && <p className="text-slate-400 text-xs mt-0.5 font-mono">{sub}</p>}
      </div>
    </div>
  )
}

export default function Overview() {
  const { data: stats } = useQuery({ queryKey: ['overview-stats'], queryFn: api.overviewStats, refetchInterval: 30_000 })
  const { data: alerts } = useQuery({ queryKey: ['recent-alerts'], queryFn: () => api.recentAlerts(10), refetchInterval: 30_000 })
  const { data: riskDist } = useQuery({ queryKey: ['risk-dist'], queryFn: api.riskDistribution, refetchInterval: 30_000 })
  const { data: volume } = useQuery({ queryKey: ['volume'], queryFn: api.volumeOverTime, refetchInterval: 30_000 })

  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="font-display font-800 text-2xl text-slate-900">Overview</h1>
        <p className="text-slate-500 text-sm mt-1">Real-time AML pipeline status</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Total Transactions" value={stats?.total_transactions ?? '—'} icon={Zap} accent="bg-blue-500" />
        <StatCard label="Verified" value={stats?.verified ?? '—'} icon={CheckCircle} accent="bg-green-500" />
        <StatCard label="Suspicious" value={stats?.suspicious ?? '—'} icon={AlertTriangle} accent="bg-red-500" />
        <StatCard label="Detection Rate" value={stats ? `${stats.detection_rate}%` : '—'} icon={TrendingUp} accent="bg-purple-500" />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="font-display font-600 text-slate-800 mb-4">Risk Distribution</h2>
          {riskDist?.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={riskDist} dataKey="count" nameKey="risk_level" innerRadius={60} outerRadius={90} paddingAngle={3}>
                  {riskDist.map((d) => <Cell key={d.risk_level} fill={RISK_COLORS[d.risk_level] ?? '#94a3b8'} />)}
                </Pie>
                <Tooltip formatter={(v, n) => [v, String(n).toUpperCase()]} />
              </PieChart>
            </ResponsiveContainer>
          ) : <p className="text-slate-400 text-sm text-center py-16">No data yet</p>}
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="font-display font-600 text-slate-800 mb-4">Volume Over Time</h2>
          {volume?.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={volume} margin={{ left: -20 }}>
                <XAxis dataKey="hour" tickFormatter={(v) => v.slice(11, 16)} tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                {(['low', 'medium', 'high', 'blocked'] as const).map((k) => (
                  <Bar key={k} dataKey={k} stackId="a" fill={RISK_COLORS[k]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-slate-400 text-sm text-center py-16">No data yet</p>}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h2 className="font-display font-600 text-slate-800 mb-4">Recent Alerts</h2>
        {alerts?.length ? (
          <div className="space-y-2">
            {alerts.map((a) => (
              <div key={a.transaction_id} className="flex items-center gap-4 px-4 py-3 rounded-lg bg-slate-50 border border-slate-100">
                <RiskBadge level={a.risk_level} />
                <span className="font-mono text-sm text-slate-700 font-medium w-32 truncate">{a.account_id}</span>
                <span className="font-mono text-sm text-slate-900">${a.amount_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                <span className="text-slate-500 text-xs flex-1">{a.triggered_rules.join(', ') || '—'}</span>
                <span className="text-slate-400 text-xs font-mono">{a.verified_at}</span>
              </div>
            ))}
          </div>
        ) : <p className="text-slate-400 text-sm">No suspicious transactions detected.</p>}
      </div>
    </div>
  )
}
