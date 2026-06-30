interface FraudGaugeProps {
  score: number
  showLabel?: boolean
}

export function FraudGauge({ score, showLabel = true }: FraudGaugeProps) {
  const getRiskLevel = (score: number) => {
    if (score < 25) return 'LOW'
    if (score < 50) return 'MEDIUM'
    if (score < 75) return 'HIGH'
    return 'CRITICAL'
  }

  const getColors = (score: number) => {
    if (score < 25) {
      return {
        gauge: 'text-green-600',
        bg: 'bg-green-100',
        text: 'text-green-900',
      }
    } else if (score < 50) {
      return {
        gauge: 'text-yellow-600',
        bg: 'bg-yellow-100',
        text: 'text-yellow-900',
      }
    } else if (score < 75) {
      return {
        gauge: 'text-orange-600',
        bg: 'bg-orange-100',
        text: 'text-orange-900',
      }
    }
    return {
      gauge: 'text-red-600',
      bg: 'bg-red-100',
      text: 'text-red-900',
    }
  }

  const colors = getColors(score)
  const circumference = 2 * Math.PI * 45
  const strokeDashoffset = circumference - (score / 100) * circumference

  return (
    <div className={`p-8 rounded-lg border border-slate-200 ${colors.bg}`}>
      {showLabel && (
        <h3 className={`font-semibold text-sm mb-6 ${colors.text}`}>
          Fraud Risk Score
        </h3>
      )}
      <div className="flex justify-center">
        <div className="relative w-32 h-32">
          <svg className="w-full h-full transform -rotate-90">
            <circle
              cx="64"
              cy="64"
              r="45"
              fill="none"
              stroke="currentColor"
              strokeWidth="8"
              className="text-slate-200"
            />
            <circle
              cx="64"
              cy="64"
              r="45"
              fill="none"
              stroke="currentColor"
              strokeWidth="8"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              className={`transition-all duration-1000 ${colors.gauge}`}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-4xl font-bold ${colors.gauge}`}>{score}</span>
            <span className={`text-xs font-semibold mt-1 ${colors.text}`}>
              {getRiskLevel(score)}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
