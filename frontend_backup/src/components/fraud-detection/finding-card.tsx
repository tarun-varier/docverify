'use client'

import { useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'

interface FindingCardProps {
  code: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH'
  description: string
  details?: string
}

export function FindingCard({
  code,
  severity,
  description,
  details,
}: FindingCardProps) {
  const [isOpen, setIsOpen] = useState(false)

  const severityColor =
    severity === 'HIGH'
      ? 'bg-red-50 border-red-200'
      : severity === 'MEDIUM'
        ? 'bg-yellow-50 border-yellow-200'
        : 'bg-blue-50 border-blue-200'

  const severityBadge =
    severity === 'HIGH'
      ? 'bg-red-100 text-red-700'
      : severity === 'MEDIUM'
        ? 'bg-yellow-100 text-yellow-700'
        : 'bg-blue-100 text-blue-700'

  return (
    <div className={`border rounded-lg ${severityColor} overflow-hidden`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full p-4 flex items-center justify-between hover:opacity-80 transition-opacity"
      >
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-orange-600 flex-shrink-0" />
          <div className="text-left">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`text-xs font-semibold px-2 py-1 rounded ${severityBadge}`}
              >
                {severity}
              </span>
              <span className="font-mono text-xs text-slate-600">{code}</span>
            </div>
            <p className="text-sm text-slate-700">{description}</p>
          </div>
        </div>
        {isOpen ? (
          <ChevronUp className="w-5 h-5 text-slate-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-slate-400" />
        )}
      </button>
      {isOpen && details && (
        <div className="px-4 py-3 border-t bg-white/50">
          <p className="text-sm text-slate-700">{details}</p>
        </div>
      )}
    </div>
  )
}
