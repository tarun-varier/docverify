interface StatusBadgeProps {
  status: 'Verified' | 'Mismatch' | 'Match' | 'Invalid' | 'Pending' | 'Manual Review'
  label?: string
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const getStyles = (status: string) => {
    switch (status) {
      case 'Verified':
      case 'Match':
        return 'bg-green-100 text-green-700'
      case 'Mismatch':
      case 'Invalid':
        return 'bg-red-100 text-red-700'
      case 'Manual Review':
        return 'bg-yellow-100 text-yellow-700'
      case 'Pending':
      default:
        return 'bg-slate-100 text-slate-700'
    }
  }

  return (
    <div className="flex items-center gap-2">
      {label && <span className="text-xs text-slate-600">{label}</span>}
      <span className={`text-xs font-semibold px-2 py-1 rounded ${getStyles(status)}`}>
        {status}
      </span>
    </div>
  )
}
