import { useEffect, useState } from 'react'
import { CheckCircle, Circle, LogOut } from 'lucide-react'

interface PipelineStep {
  id: number
  name: string
  description: string
  status: 'pending' | 'processing' | 'completed'
}

const initialSteps: PipelineStep[] = [
  {
    id: 1,
    name: 'OCR & Field Extraction',
    description: 'Extracting text and data from documents',
    status: 'pending',
  },
  {
    id: 2,
    name: 'Digital Forensics',
    description: 'Analyzing document authenticity',
    status: 'pending',
  },
  {
    id: 3,
    name: 'Cross-document Validation',
    description: 'Comparing data across documents',
    status: 'pending',
  },
  {
    id: 4,
    name: 'Registry Verification',
    description: 'Verifying against government databases',
    status: 'pending',
  },
  {
    id: 5,
    name: 'Fraud Scoring',
    description: 'Computing fraud risk assessment',
    status: 'pending',
  },
  {
    id: 6,
    name: 'AI Underwriting',
    description: 'Generating underwriting decision',
    status: 'pending',
  },
  {
    id: 7,
    name: 'Audit Logging',
    description: 'Recording analysis history',
    status: 'pending',
  },
]

export default function Processing() {
  const [steps, setSteps] = useState<PipelineStep[]>(initialSteps)
  const [currentStep, setCurrentStep] = useState(0)

  useEffect(() => {
    if (currentStep >= steps.length) {
      setTimeout(() => {
        window.location.href = '/results'
      }, 1500)
      return
    }

    setSteps((prev) =>
      prev.map((step, idx) => {
        if (idx === currentStep) {
          return { ...step, status: 'processing' }
        }
        return step
      })
    )

    const timer = setTimeout(() => {
      setSteps((prev) =>
        prev.map((step, idx) => {
          if (idx === currentStep) {
            return { ...step, status: 'completed' }
          }
          return step
        })
      )
      setCurrentStep((prev) => prev + 1)
    }, 1200 + Math.random() * 800)

    return () => clearTimeout(timer)
  }, [currentStep, steps.length])

  const completedCount = steps.filter((s) => s.status === 'completed').length
  const progress = (completedCount / steps.length) * 100

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

      <main className="max-w-2xl mx-auto px-6 py-10">
        <div className="p-8 bg-white border border-slate-200 rounded-xl shadow-sm text-center mb-8">
          <h2 className="text-xl font-bold text-slate-900 mb-2">
            Document Auditing Pipeline
          </h2>
          <p className="text-sm text-slate-600 mb-6">
            Executing local deterministic models and anti-tamper scans...
          </p>

          <div className="flex justify-center mb-6">
            <div className="relative w-36 h-36">
              <svg className="w-full h-full transform -rotate-90">
                <circle
                  cx="72"
                  cy="72"
                  r="55"
                  fill="none"
                  stroke="#e2e8f0"
                  strokeWidth="8"
                />
                <circle
                  cx="72"
                  cy="72"
                  r="55"
                  fill="none"
                  stroke="var(--canara-blue)"
                  strokeWidth="8"
                  strokeDasharray={2 * Math.PI * 55}
                  strokeDashoffset={2 * Math.PI * 55 - (progress / 100) * (2 * Math.PI * 55)}
                  className="transition-all duration-300"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-extrabold text-blue-700">{progress.toFixed(0)}%</span>
                <span className="text-xs font-bold text-slate-500 mt-1 uppercase tracking-wider">
                  {completedCount} of {steps.length} Done
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 px-1">
            Verification Pipeline Status
          </h3>
          {steps.map((step, index) => (
            <div key={step.id}>
              <div
                className={`p-4 rounded-lg border transition-all ${
                  step.status === 'completed'
                    ? 'bg-green-50 border-green-200'
                    : step.status === 'processing'
                      ? 'bg-blue-50 border-blue-200 shadow-sm'
                      : 'bg-white border-slate-200'
                }`}
              >
                <div className="flex items-start gap-4">
                  <div className="mt-1 flex-shrink-0">
                    {step.status === 'completed' ? (
                      <div className="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center">
                        <CheckCircle className="w-5 h-5 text-white" />
                      </div>
                    ) : step.status === 'processing' ? (
                      <div className="w-6 h-6 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
                    ) : (
                      <Circle className="w-6 h-6 text-slate-300" />
                    )}
                  </div>
                  <div className="flex-1">
                    <h3
                      className={`font-semibold text-sm ${
                        step.status === 'completed'
                          ? 'text-green-900 font-bold'
                          : step.status === 'processing'
                            ? 'text-blue-900 font-bold'
                            : 'text-slate-900'
                      }`}
                    >
                      Layer {step.id} — {step.name}
                    </h3>
                    <p
                      className={`text-xs mt-1 leading-relaxed ${
                        step.status === 'completed'
                          ? 'text-green-700'
                          : step.status === 'processing'
                            ? 'text-blue-700'
                            : 'text-slate-500'
                      }`}
                    >
                      {step.description}
                    </p>
                  </div>
                </div>
              </div>

              {index < steps.length - 1 && (
                <div className="ml-7 h-4 bg-slate-200 w-0.5 my-1" />
              )}
            </div>
          ))}
        </div>

        <div className="mt-12 text-center">
          <p className="text-xs text-slate-500">
            This verification run is recorded on the Canara secure audit log ledger.
          </p>
        </div>
      </main>
    </div>
  )
}