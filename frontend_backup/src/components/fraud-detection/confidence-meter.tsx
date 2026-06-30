interface ConfidenceMeterProps {
  score: number // 0-1 or 0-100
  label?: string
  showPercentage?: boolean
}

export function ConfidenceMeter({
  score,
  label = 'Confidence',
  showPercentage = true,
}: ConfidenceMeterProps) {
  // Normalize score to 0-100
  const normalizedScore = score > 1 ? score : score * 100

  const getColor = (score: number) => {
    if (score >= 80) return 'bg-green-500'
    if (score >= 60) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  const getText = (score: number) => {
    if (score >= 80) return 'text-green-700'
    if (score >= 60) return 'text-yellow-700'
    return 'text-red-700'
  }

  return (
    <div>
      {label && <p className="text-xs font-semibold text-slate-600 mb-2">{label}</p>}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all ${getColor(normalizedScore)}`}
            style={{ width: `${normalizedScore}%` }}
          />
        </div>
        {showPercentage && (
          <span className={`text-xs font-semibold ${getText(normalizedScore)}`}>
            {Math.round(normalizedScore)}%
          </span>
        )}
      </div>
    </div>
  )
}
