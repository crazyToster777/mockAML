const styles: Record<string, string> = {
  low:     'bg-green-100  text-green-700  ring-green-200',
  medium:  'bg-amber-100  text-amber-700  ring-amber-200',
  high:    'bg-red-100    text-red-700    ring-red-200',
  blocked: 'bg-purple-100 text-purple-700 ring-purple-200',
}

export default function RiskBadge({ level }: { level: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium ring-1 ring-inset ${styles[level] ?? 'bg-slate-100 text-slate-600 ring-slate-200'}`}>
      {level.toUpperCase()}
    </span>
  )
}
