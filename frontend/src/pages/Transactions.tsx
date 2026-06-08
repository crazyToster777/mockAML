import { useQuery } from '@tanstack/react-query'
import {
  createColumnHelper, flexRender, getCoreRowModel, useReactTable,
} from '@tanstack/react-table'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { api, TransactionRow } from '../api/client'
import RiskBadge from '../components/RiskBadge'

const RISK_LEVELS = ['low', 'medium', 'high', 'blocked']
const col = createColumnHelper<TransactionRow>()

const columns = [
  col.accessor('account_id',      { header: 'Account', cell: i => <span className="font-mono text-sm">{i.getValue()}</span> }),
  col.accessor('risk_level',      { header: 'Risk',    cell: i => <RiskBadge level={i.getValue()} /> }),
  col.accessor('amount_usd',      { header: 'Amount (USD)', cell: i => <span className="font-mono">${i.getValue().toLocaleString('en-US', { minimumFractionDigits: 2 })}</span> }),
  col.accessor('triggered_rules', { header: 'Triggered Rules', cell: i => <span className="text-slate-600 text-xs">{(i.getValue() as string[]).join(', ') || '—'}</span> }),
  col.accessor('verified_at',     { header: 'Verified At', cell: i => <span className="font-mono text-xs text-slate-500">{i.getValue()}</span> }),
  col.accessor('notes',           { header: 'Notes', cell: i => <span className="text-slate-500 text-xs truncate max-w-xs block">{i.getValue() || '—'}</span> }),
]

export default function Transactions() {
  const [page, setPage] = useState(0)
  const [selectedRisk, setSelectedRisk] = useState<string[]>(RISK_LEVELS)
  const [accountId, setAccountId] = useState('')
  const [minAmount, setMinAmount] = useState('')
  const limit = 50

  const params: Record<string, string> = {
    limit: String(limit),
    offset: String(page * limit),
    ...(accountId ? { account_id: accountId } : {}),
    ...(minAmount  ? { min_amount: minAmount } : {}),
  }
  selectedRisk.forEach(r => { params['risk_level'] = r })
  // build proper multi-value query
  const qs = selectedRisk.map(r => `risk_level=${r}`).join('&')
    + `&limit=${limit}&offset=${page * limit}`
    + (accountId ? `&account_id=${encodeURIComponent(accountId)}` : '')
    + (minAmount  ? `&min_amount=${minAmount}` : '')

  const { data, isFetching } = useQuery({
    queryKey: ['transactions', page, selectedRisk, accountId, minAmount],
    queryFn: () => fetch(`/api/transactions?${qs}`).then(r => r.json()),
  })

  const table = useReactTable({
    data: data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: Math.ceil((data?.total ?? 0) / limit),
  })

  const totalPages = Math.ceil((data?.total ?? 0) / limit)

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="font-display font-800 text-2xl text-slate-900">Transactions</h1>
        <p className="text-slate-500 text-sm mt-1">{data?.total ?? 0} records total</p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap gap-6 items-end">
        <div>
          <p className="text-xs text-slate-500 mb-2 font-medium">Risk Level</p>
          <div className="flex gap-2">
            {RISK_LEVELS.map(r => (
              <label key={r} className="flex items-center gap-1.5 cursor-pointer">
                <input type="checkbox" checked={selectedRisk.includes(r)}
                  onChange={e => setSelectedRisk(prev => e.target.checked ? [...prev, r] : prev.filter(x => x !== r))}
                  className="rounded border-slate-300" />
                <RiskBadge level={r} />
              </label>
            ))}
          </div>
        </div>
        <div>
          <p className="text-xs text-slate-500 mb-2 font-medium">Account ID</p>
          <input value={accountId} onChange={e => { setAccountId(e.target.value); setPage(0) }}
            placeholder="Search..." className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm w-40 focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <p className="text-xs text-slate-500 mb-2 font-medium">Min Amount ($)</p>
          <input type="number" value={minAmount} onChange={e => { setMinAmount(e.target.value); setPage(0) }}
            placeholder="0" className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm w-28 focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className={`overflow-x-auto transition-opacity ${isFetching ? 'opacity-60' : ''}`}>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              {table.getHeaderGroups().map(hg => (
                <tr key={hg.id}>
                  {hg.headers.map(h => (
                    <th key={h.id} className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                      {flexRender(h.column.columnDef.header, h.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-slate-100">
              {table.getRowModel().rows.length ? table.getRowModel().rows.map(row => (
                <tr key={row.id} className="hover:bg-slate-50 transition-colors">
                  {row.getVisibleCells().map(cell => (
                    <td key={cell.id} className="px-4 py-3">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              )) : (
                <tr><td colSpan={6} className="px-4 py-12 text-center text-slate-400">No records found</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-4 py-3 border-t border-slate-200 flex items-center justify-between">
          <p className="text-sm text-slate-500 font-mono">
            {page * limit + 1}–{Math.min((page + 1) * limit, data?.total ?? 0)} of {data?.total ?? 0}
          </p>
          <div className="flex gap-2">
            <button onClick={() => setPage(p => p - 1)} disabled={page === 0}
              className="p-1.5 rounded-lg border border-slate-200 disabled:opacity-40 hover:bg-slate-100 transition-colors">
              <ChevronLeft size={16} />
            </button>
            <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages - 1}
              className="p-1.5 rounded-lg border border-slate-200 disabled:opacity-40 hover:bg-slate-100 transition-colors">
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
