import { BarChart2, GitMerge, LayoutDashboard, List, ShieldAlert, Zap } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const links = [
  { to: '/',               icon: LayoutDashboard, label: 'Overview' },
  { to: '/transactions',   icon: List,            label: 'Transactions' },
  { to: '/analytics',      icon: BarChart2,       label: 'Analytics' },
  { to: '/reconciliation', icon: GitMerge,        label: 'Reconciliation' },
  { to: '/produce',        icon: Zap,             label: 'Produce' },
]

export default function Sidebar() {
  return (
    <aside className="w-56 bg-slate-900 flex flex-col shrink-0">
      <div className="px-6 py-6 border-b border-slate-700/60">
        <div className="flex items-center gap-2">
          <ShieldAlert className="text-blue-400" size={20} />
          <span className="font-display font-700 text-white text-lg tracking-tight">AML Guard</span>
        </div>
        <p className="text-slate-500 text-xs mt-1 font-mono">Anti-Money Laundering</p>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 ${
                isActive
                  ? 'bg-blue-600 text-white font-medium'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-slate-700/60">
        <p className="text-slate-600 text-xs font-mono">v1.0.0</p>
      </div>
    </aside>
  )
}
