'use client'

import { useState } from 'react'
import { File, ChevronDown, ChevronUp, Copy } from 'lucide-react'

interface DocumentCardProps {
  filename: string
  documentType: string
  pageCount: number
  ocrUsed: boolean
  sha256?: string
}

export function DocumentCard({
  filename,
  documentType,
  pageCount,
  ocrUsed,
  sha256 = 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6',
}: DocumentCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden bg-white hover:shadow-md transition-shadow">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-100 rounded flex items-center justify-center">
            <File className="w-5 h-5 text-blue-600" />
          </div>
          <div className="text-left min-w-0">
            <p className="font-medium text-slate-900 truncate">{filename}</p>
            <p className="text-xs text-slate-600 mt-1">
              {documentType} • {pageCount} page{pageCount > 1 ? 's' : ''}
            </p>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-slate-400 flex-shrink-0" />
        ) : (
          <ChevronDown className="w-5 h-5 text-slate-400 flex-shrink-0" />
        )}
      </button>

      {isExpanded && (
        <div className="border-t border-slate-200 p-4 bg-slate-50 space-y-3">
          <div>
            <h4 className="text-xs font-semibold text-slate-700 mb-1">
              Document Type
            </h4>
            <p className="text-sm text-slate-900">{documentType}</p>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-slate-700 mb-1">
              Pages
            </h4>
            <p className="text-sm text-slate-900">{pageCount}</p>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-slate-700 mb-1">
              OCR Status
            </h4>
            <p className="text-sm text-slate-900">
              {ocrUsed ? 'Applied' : 'Not Applied'}
            </p>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-slate-700 mb-1">
              SHA256 Hash
            </h4>
            <div className="flex items-center gap-2">
              <code className="text-xs font-mono text-slate-600 break-all">
                {sha256}
              </code>
              <button className="p-1 hover:bg-white rounded transition-colors">
                <Copy className="w-4 h-4 text-slate-400" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
