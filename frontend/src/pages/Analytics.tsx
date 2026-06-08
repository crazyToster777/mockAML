import { useQuery } from '@tanstack/react-query'
import {
  Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../api/client'

export default function Analytics() {
  const { data: rules } = useQuery({ queryKey: ['triggered-rules'], queryFn: api.triggeredRules })
  const { data: cumulative } = useQuery({ queryKey: ['cumulative-suspicious'], queryFn: api.cumulativeSuspicious })

  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="font-display font-800 text-2xl text-slate-900">Analytics</h1>
        <p className="text-slate-500 text-sm mt-1">Rule performance and suspicious transaction trends</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="font-display font-600 text-slate-800 mb-1">Triggered Rules</h2>
        <p className="text-slate-400 text-xs mb-6">Frequency of each AML rule being triggered</p>
        {rules?.length ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={rules} layout="vertical" margin={{ left: 20, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis type="category" dataKey="rule" width={160} tick={{ fontSize: 11, fill: '#64748b' }} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 8, color: '#f1f5f9', fontSize: 12 }}
                cursor={{ fill: '#f8fafc' }}
              />
              <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : <p className="text-slate-400 text-sm py-16 text-center">No data yet</p>}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="font-display font-600 text-slate-800 mb-1">Cumulative Suspicious Transactions</h2>
        <p className="text-slate-400 text-xs mb-6">Running total of high-risk + blocked transactions over time</p>
        {cumulative?.length ? (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={cumulative} margin={{ left: -10, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="verified_at"
                tickFormatter={(v) => new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                tick={{ fontSize: 11, fill: '#94a3b8' }}
              />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} allowDecimals={false} />
              <Tooltip
                labelFormatter={(v) => new Date(v).toLocaleString()}
                contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 8, color: '#f1f5f9', fontSize: 12 }}
              />
              <Line
                type="monotone" dataKey="cumulative" stroke="#ef4444"
                strokeWidth={2} dot={false} activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : <p className="text-slate-400 text-sm py-16 text-center">No data yet</p>}
      </div>
    </div>
  )
}
