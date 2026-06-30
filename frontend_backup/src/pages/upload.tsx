import { useState, useCallback } from 'react'
import { Upload as UploadIcon, File, X, LogOut } from 'lucide-react'

interface UploadedFile {
  id: string
  name: string
  size: number
  type: string
  fileObj: File
}

const API_BASE_URL = (() => {
  const configuredUrl = import.meta.env.VITE_API_URL ?? import.meta.env.VITE_BACKEND_URL
  if (configuredUrl) {
    return configuredUrl.replace(/\/$/, '')
  }

  if (typeof window !== 'undefined' && window.location.hostname) {
    const host = window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname
    return `${window.location.protocol}//${host}:8000`
  }

  return 'http://127.0.0.1:8000'
})()

export default function Upload() {
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [errorInfo, setErrorInfo] = useState<any>(null)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setIsDragging(false)
  }, [])

  const processFiles = useCallback((fileList: FileList) => {
    const newFiles = Array.from(fileList).map((file) => ({
      id: Math.random().toString(36).substr(2, 9),
      name: file.name,
      size: file.size,
      type: file.type,
      fileObj: file,
    }))
    setFiles((prev) => [...prev, ...newFiles])
    setErrorInfo(null)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)
      processFiles(e.dataTransfer.files)
    },
    [processFiles]
  )

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        processFiles(e.target.files)
      }
    },
    [processFiles]
  )

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
    setErrorInfo(null)
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
  }

  const handleAnalyze = async () => {
    if (files.length === 0) {
      setErrorInfo('Choose a file before uploading.')
      return
    }

    setIsUploading(true)
    setErrorInfo(null)
    localStorage.removeItem('docverify_response')

    const fileToUpload = files[0].fileObj
    const formData = new FormData()
    formData.append('file', fileToUpload)

    try {
      const result = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData,
      })

      const payload = await result.json().catch(() => null)

      if (!result.ok) {
        if (payload && payload.detail) {
          if (typeof payload.detail === 'object') {
            setErrorInfo(payload.detail)
          } else {
            setErrorInfo(String(payload.detail))
          }
        } else {
          setErrorInfo('Security Gateway or Backend returned an upload error.')
        }
        return
      }

      localStorage.setItem('docverify_response', JSON.stringify(payload))
      window.location.href = '/processing'
    } catch (uploadError) {
      const msg = uploadError instanceof Error ? uploadError.message : 'Unable to communicate with backend.'
      setErrorInfo(msg)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white shadow-sm">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="canara-logo flex-shrink-0" />
            <div className="border-l border-slate-300 pl-4">
              <h1 className="text-xl font-bold text-blue-700 flex items-center gap-2 mb-0.5">
                कैनरा बैंक <span className="text-slate-400">|</span> Canara Bank
              </h1>
              <p className="text-xs text-amber-900 font-semibold tracking-wider italic">
                Together we can
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Risk & Underwriting Dept
              </div>
              <div className="text-xs font-bold text-blue-600 mt-0.5">
                Officer ID: #CNB-9024
              </div>
            </div>
            <button
              onClick={() => {
                window.location.href = '/login'
              }}
              className="px-3 py-1.5 border border-slate-300 hover:border-red-500 hover:text-red-650 text-slate-700 hover:text-red-600 rounded-lg text-xs font-bold transition-colors flex items-center gap-1 bg-white cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10">
        <div className="mb-8 border-b border-slate-200 pb-6 flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 mb-1">
              DocVerify AI — Loan Fraud Auditing Workspace
            </h2>
            <p className="text-sm text-slate-600">
              Upload customer verification records to initiate deterministic anti-tampering and underwriting scans.
            </p>
          </div>
          <div className="px-3 py-1.5 bg-yellow-100 border border-yellow-250 text-amber-900 rounded-lg text-xs font-bold uppercase tracking-wider">
            Secure Sandbox Active
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column: Upload Area */}
          <div className="lg:col-span-2 space-y-6">
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-xl p-10 text-center transition-all ${
                isDragging
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-slate-300 bg-white hover:border-blue-500'
              }`}
            >
              <div className="flex flex-col items-center gap-4">
                <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center">
                  <UploadIcon className="w-8 h-8 text-blue-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 mb-1">
                    Drag & drop customer documents here
                  </h3>
                  <p className="text-sm text-slate-600 mb-4">or click to browse files from local machine</p>
                </div>
                <label className="cursor-pointer">
                  <input
                    type="file"
                    multiple
                    onChange={handleFileInput}
                    className="hidden"
                    accept=".pdf,.png,.jpg,.jpeg,.tiff"
                  />
                  <span className="inline-block px-6 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors shadow-sm">
                    Choose Files
                  </span>
                </label>
                <p className="text-xs text-slate-500 mt-2">
                  Supported formats: PDF, PNG, JPG, JPEG, TIFF (Max 10MB per file)
                </p>
              </div>
            </div>

            {errorInfo && (
              <div className="mt-6 rounded-2xl border border-red-500/30 bg-red-500/10 p-5 text-red-300 shadow-xl animate-fade-in text-left">
                {typeof errorInfo === 'object' ? (
                  <div>
                    <div className="flex items-center justify-between border-b border-red-500/20 pb-3 mb-3">
                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-1 rounded-md bg-red-500/20 text-red-400 text-xs font-extrabold tracking-wider uppercase border border-red-500/30">
                          {errorInfo.status || 'REJECTED'}
                        </span>
                        <span className="text-xs font-bold text-red-300 uppercase tracking-wide">
                          Threat Level: {errorInfo.threat || 'HIGH'}
                        </span>
                      </div>
                      <span className="text-xs text-red-400/80 font-mono">Layer 0 Gateway Block</span>
                    </div>
                    <p className="text-sm font-bold text-red-100 mb-2">Layer 0 Security Gateway Blocked This Document:</p>
                    <ul className="list-disc list-inside space-y-1 text-xs text-red-300 font-mono bg-slate-950/60 p-3 rounded-xl border border-red-500/20">
                      {errorInfo.findings && errorInfo.findings.length > 0 ? (
                        errorInfo.findings.map((f: string, i: number) => <li key={i}>{f}</li>)
                      ) : (
                        <li>{errorInfo.detail || 'Suspicious or corrupted PDF structure detected.'}</li>
                      )}
                    </ul>
                  </div>
                ) : (
                  <div className="flex items-center gap-3">
                    <svg className="w-5 h-5 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <span className="text-sm font-medium">{errorInfo}</span>
                  </div>
                )}
              </div>
            )}

            {files.length > 0 && (
              <div className="p-6 bg-white border border-slate-200 rounded-xl">
                <h3 className="text-base font-semibold text-slate-900 mb-4">
                  Active Document Queue ({files.length})
                </h3>
                <div className="grid gap-3">
                  {files.map((file) => (
                    <div
                      key={file.id}
                      className="flex items-center gap-4 p-3 bg-slate-50 border border-slate-200 rounded-lg hover:shadow-sm transition-shadow"
                    >
                      <div className="w-10 h-10 bg-blue-100 rounded flex items-center justify-center flex-shrink-0">
                        <File className="w-5 h-5 text-blue-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-900 truncate">
                          {file.name}
                        </p>
                        <p className="text-xs text-slate-500">
                          {formatFileSize(file.size)}
                        </p>
                      </div>
                      <button
                        onClick={() => removeFile(file.id)}
                        className="p-2 text-slate-400 hover:text-red-600 transition-colors"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
                <div className="mt-6 flex justify-center">
                  <button
                    onClick={handleAnalyze}
                    disabled={isUploading}
                    className="px-8 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:bg-slate-400 transition-colors shadow-md flex items-center gap-2"
                  >
                    {isUploading ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin rounded-full" />
                        Analyzing Documents...
                      </>
                    ) : (
                      'Analyze Documents'
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Policies & Help */}
          <div className="lg:col-span-1 space-y-6">
            <div className="p-6 bg-white border border-slate-200 rounded-xl">
              <h3 className="text-base font-bold text-slate-900 mb-4 pb-2 border-b border-slate-100">
                Compliance Standards Checklist
              </h3>
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <div className="w-5 h-5 bg-green-100 rounded-full flex items-center justify-center text-green-700 text-xs font-bold flex-shrink-0 mt-0.5">✓</div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-800">RBI KYC Circular 2024/15</h4>
                    <p className="text-xs text-slate-500">Ensures strict identity verification checks are passed.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-5 h-5 bg-green-100 rounded-full flex items-center justify-center text-green-700 text-xs font-bold flex-shrink-0 mt-0.5">✓</div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-800">Anti-Tampering Integrity Scan</h4>
                    <p className="text-xs text-slate-500">Detects digital modification, font mismatches, and photo edits.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-5 h-5 bg-green-100 rounded-full flex items-center justify-center text-green-700 text-xs font-bold flex-shrink-0 mt-0.5">✓</div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-800">Income Tax (ITR) Validation</h4>
                    <p className="text-xs text-slate-500">Cross-checks salary slips with official declarations.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-5 h-5 bg-green-100 rounded-full flex items-center justify-center text-green-700 text-xs font-bold flex-shrink-0 mt-0.5">✓</div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-800">Bilingual Name Alignment</h4>
                    <p className="text-xs text-slate-500">Matches details in English and regional formats across IDs.</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="p-6 bg-slate-900 border border-slate-200 rounded-xl">
              <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                Security & Data Privacy
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                In compliance with banking regulations, all uploads are processed through Canara Bank's sandboxed microservices. No document details are sent to external third parties.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}