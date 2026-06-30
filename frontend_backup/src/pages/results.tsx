import { useState } from 'react'
import {
  AlertTriangle,
  CheckCircle,
  Download,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  CheckCircle2,
  LogOut,
} from 'lucide-react'

// Mock data - replace with real API data
const mockResults = {
  fraudScore: 74,
  riskLevel: 'CRITICAL',
  recommendedAction: 'Hold disbursement. Complete enhanced due diligence.',
  summary:
    'Multiple anomalies detected including possible document backdating, salary mismatch across documents, and unusual metadata patterns.',
  findings: [
    {
      code: 'META_POSSIBLE_BACKDATING',
      severity: 'HIGH',
      description: 'Document metadata indicates possible backdating.',
    },
    {
      code: 'SALARY_MISMATCH',
      severity: 'HIGH',
      description: 'Salary information differs across submitted documents.',
    },
    {
      code: 'UNUSUAL_FONT_PATTERNS',
      severity: 'MEDIUM',
      description:
        'Font patterns suggest document may have been modified.',
    },
  ],
  recommendations: [
    'Reject PAN document',
    'Request certified copy',
    'Video KYC',
    'Manual address verification',
  ],
  documents: [
    { name: 'pan_card.pdf', type: 'PAN', pages: 1, pages_ocrd: 1 },
    { name: 'aadhar.jpg', type: 'Aadhar', pages: 1, pages_ocrd: 1 },
    { name: 'address_proof.pdf', type: 'Address Proof', pages: 2, pages_ocrd: 2 },
  ],
  extractedFields: [
    {
      field: 'Applicant Name',
      value: 'John Doe',
      method: 'Regex',
      confidence: 0.98,
      status: 'Verified',
    },
    {
      field: 'PAN',
      value: 'ABCDE1234F',
      method: 'Template',
      confidence: 0.95,
      status: 'Verified',
    },
    {
      field: 'Date of Birth',
      value: '15/03/1985',
      method: 'OCR',
      confidence: 0.72,
      status: 'Manual Review',
    },
  ],
  crossDocChecks: [
    { document: 'PAN', field: 'Name', status: 'Match' },
    { document: 'Aadhar', field: 'Address', status: 'Mismatch' },
    { document: 'Income', field: 'Salary', status: 'Mismatch' },
  ],
  registryVerification: [
    { name: 'PAN', status: 'Invalid', explanation: 'Invalid PAN format' },
    { name: 'CIN', status: 'Verified', explanation: 'Valid CIN found' },
    {
      name: 'Survey Number',
      status: 'Verified',
      explanation: 'Address verified',
    },
  ],
  audit: {
    caseId: 'CASE-2024-001234',
    timestamp: '2024-01-15 14:32:45',
    hash: 'a1b2c3d4e5f6g7h8i9j0',
    elapsedTime: '45.32s',
    status: 'Completed',
  },
}

function FraudGauge({ score, recommendedAction }: { score: number; recommendedAction: string }) {
  let color = 'text-green-600'
  let bgColor = 'bg-green-100'
  let textColor = 'text-green-900'

  if (score < 25) {
    color = 'text-green-600'
    bgColor = 'bg-green-100'
    textColor = 'text-green-900'
  } else if (score < 50) {
    color = 'text-yellow-600'
    bgColor = 'bg-yellow-100'
    textColor = 'text-yellow-900'
  } else if (score < 75) {
    color = 'text-orange-600'
    bgColor = 'bg-orange-100'
    textColor = 'text-orange-900'
  } else {
    color = 'text-red-600'
    bgColor = 'bg-red-100'
    textColor = 'text-red-900'
  }

  const circumference = 2 * Math.PI * 45
  const strokeDashoffset = circumference - (score / 100) * circumference

  return (
    <div className={`p-8 rounded-lg border border-slate-200 ${bgColor}`}>
      <h3 className={`font-semibold text-sm mb-6 ${textColor}`}>
        Fraud Risk Score
      </h3>
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
              className={`transition-all duration-1000 ${color}`}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-4xl font-bold ${color}`}>{score}</span>
            <span className={`text-xs font-semibold mt-1 ${textColor}`}>
              {score < 25 ? 'LOW' : score < 50 ? 'MEDIUM' : score < 75 ? 'HIGH' : 'CRITICAL'}
            </span>
          </div>
        </div>
      </div>
      <div className="mt-6 pt-6 border-t border-slate-300">
        <p className={`font-semibold text-sm mb-2 ${textColor}`}>
          Recommended Action
        </p>
        <p className={`text-sm leading-relaxed ${textColor}`}>
          {recommendedAction}
        </p>
      </div>
    </div>
  )
}

function FindingCard({ code, severity, description }: any) {
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
              <span className={`text-xs font-semibold px-2 py-1 rounded ${severityBadge}`}>
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
      {isOpen && (
        <div className="px-4 py-3 border-t bg-white/50">
          <p className="text-sm text-slate-700">
            This finding requires immediate attention and should be investigated
            further before proceeding with loan disbursement.
          </p>
        </div>
      )}
    </div>
  )
}

function FieldTableRow({ field, value, method, confidence, status }: any) {
  const confidenceColor =
    confidence > 0.8
      ? 'text-green-700 bg-green-50'
      : confidence > 0.6
        ? 'text-yellow-700 bg-yellow-50'
        : 'text-red-700 bg-red-50'

  const statusIcon = status === 'Verified' ? <CheckCircle2 /> : <AlertCircle />
  const statusColor =
    status === 'Verified'
      ? 'text-green-600'
      : 'text-yellow-600'

  return (
    <tr className="border-t border-slate-202 hover:bg-slate-50 transition-colors">
      <td className="px-4 py-3 text-sm font-medium text-slate-900">{field}</td>
      <td className="px-4 py-3 text-sm text-slate-700">{value}</td>
      <td className="px-4 py-3 text-sm text-slate-600">{method}</td>
      <td className="px-4 py-3">
        <span
          className={`inline-block px-3 py-1 text-xs font-semibold rounded ${confidenceColor}`}
        >
          {(confidence * 100).toFixed(0)}%
        </span>
      </td>
      <td className="px-4 py-3 text-sm">
        <div className={`flex items-center gap-2 ${statusColor}`}>
          {statusIcon}
          <span>{status}</span>
        </div>
      </td>
    </tr>
  )
}

export default function Results() {
  const [activeTab, setActiveTab] = useState<'risk' | 'fields' | 'registry' | 'documents'>('risk')
  const [managerNote, setManagerNote] = useState('')
  const [decision, setDecision] = useState<string | null>(null)

  const realData = (() => {
    try {
      const dataStr = localStorage.getItem('docverify_response')
      return dataStr ? JSON.parse(dataStr) : null
    } catch {
      return null
    }
  })()

  const fraudScore = realData 
    ? Math.round((realData.ml_prediction?.prediction?.fraud_score ?? 0) * 100) 
    : mockResults.fraudScore

  const riskLevel = realData 
    ? (realData.ml_prediction?.prediction?.is_fraudulent ? 'CRITICAL' : 'SAFE') 
    : mockResults.riskLevel

  const verdict = realData 
    ? (realData.ml_prediction?.prediction?.verdict === 'DOCUMENT_VERIFIED_CLEAN' ? 'PASSED CLEAN' : 'SUSPICIOUS') 
    : 'CRITICAL'

  const recommendedAction = realData 
    ? (realData.ml_prediction?.prediction?.is_fraudulent 
        ? 'Hold disbursement. Complete enhanced due diligence.' 
        : 'Proceed with processing. Document verified clean.') 
    : mockResults.recommendedAction

  const summary = realData 
    ? (realData.ml_prediction?.ocr_extracted_text_sample || 'Document successfully disarmed via CDR and verified clean by ML Model.') 
    : mockResults.summary

  const findings = realData 
    ? (realData.ml_prediction?.prediction?.is_fraudulent 
        ? [
            { code: 'SUSPICIOUS_CONTENT', severity: 'HIGH', description: 'ML classification model flagged the page layouts as highly anomalous.' }
          ]
        : [])
    : mockResults.findings

  const recommendations = realData
    ? (realData.ml_prediction?.prediction?.is_fraudulent
        ? ['Reject document', 'Request certified copy', 'Manual underwriting audit review required']
        : ['Approve document routing to Ledger', 'None required'])
    : mockResults.recommendations

  const documents = realData
    ? [{ name: 'customer_upload.pdf', type: 'PDF', pages: realData.page_count, pages_ocrd: realData.page_count }]
    : mockResults.documents

  const extractedFields = realData
    ? [
        { field: 'Extracted Text Sample', value: realData.ml_prediction?.ocr_extracted_text_sample || 'None', method: 'OCR', confidence: realData.ml_prediction?.prediction?.confidence ?? 1.0, status: 'Verified' }
      ]
    : mockResults.extractedFields

  const crossDocChecks = realData
    ? [
        { document: 'PDF', field: 'Tampering Static Check', status: 'Match' },
        { document: 'ML Model', field: 'Anomaly Verdict Check', status: realData.ml_prediction?.prediction?.is_fraudulent ? 'Mismatch' : 'Match' }
      ]
    : mockResults.crossDocChecks

  const registryVerification = realData
    ? [
        { name: 'Layer 0 Security Scan', status: 'Verified', explanation: 'Static threat scan completed successfully.' },
        { name: 'CDR Sanitization', status: 'Verified', explanation: 'Document flattened to clean pixels.' }
      ]
    : mockResults.registryVerification

  const audit = realData 
    ? {
        caseId: `CASE-${realData.request_id?.slice(0, 8).toUpperCase()}`,
        timestamp: new Date().toLocaleString(),
        hash: realData.request_id || 'N/A',
        elapsedTime: '1.50s',
        status: 'Completed'
      }
    : mockResults.audit

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
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
              className="px-3 py-1.5 border border-slate-300 hover:border-red-500 hover:text-red-655 text-slate-700 hover:text-red-600 rounded-lg text-xs font-bold transition-colors flex items-center gap-1 bg-white cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Case Details Tool Strip */}
      <div className="bg-white border-b border-slate-200 py-3 px-6 shadow-sm">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className={`px-3 py-1 border rounded-lg text-xs font-bold uppercase tracking-wider ${
              riskLevel === 'CRITICAL'
                ? 'bg-red-100 border-red-200 text-red-700'
                : 'bg-green-100 border-green-200 text-green-700'
            }`}>
              {verdict}
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">
                Case ID: <span className="font-mono">{audit.caseId}</span>
              </p>
              <p className="text-xs text-slate-505 mt-0.5">
                Scanned on: {audit.timestamp} | Processing Time: {audit.elapsedTime}
              </p>
            </div>
          </div>
          <div className="flex gap-2 w-full md:w-auto justify-end">
            <button className="px-4 py-2 bg-white border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 transition-colors text-xs font-bold flex items-center gap-2">
              <Download className="w-3.5 h-3.5" />
              Download Report
            </button>
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Pane (Tabbed Details) */}
          <div className="lg:col-span-2 space-y-6">
            {/* Tabs Navigation */}
            <div className="flex border border-slate-205 bg-white rounded-xl overflow-hidden shadow-sm">
              <button
                onClick={() => setActiveTab('risk')}
                className={`tab-button flex-1 text-center ${activeTab === 'risk' ? 'active' : ''}`}
              >
                Risk Analysis & Findings
              </button>
              <button
                onClick={() => setActiveTab('fields')}
                className={`tab-button flex-1 text-center ${activeTab === 'fields' ? 'active' : ''}`}
              >
                Extracted Data
              </button>
              <button
                onClick={() => setActiveTab('registry')}
                className={`tab-button flex-1 text-center ${activeTab === 'registry' ? 'active' : ''}`}
              >
                Registry Status
              </button>
              <button
                onClick={() => setActiveTab('documents')}
                className={`tab-button flex-1 text-center ${activeTab === 'documents' ? 'active' : ''}`}
              >
                Documents
              </button>
            </div>

            {/* Tab Contents */}
            {activeTab === 'risk' && (
              <div className="space-y-6 animate-fade-in">
                {/* Underwriting Summary */}
                <div className="p-6 bg-white rounded-xl border border-slate-200 shadow-sm">
                  <h2 className="text-base font-bold text-slate-900 mb-4 pb-2 border-b border-slate-100">
                    AI Underwriting & Forensics Summary
                  </h2>
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-xs font-bold text-slate-505 uppercase tracking-wider mb-2">
                        Executive Summary
                      </h4>
                      <p className="text-sm text-slate-705 leading-relaxed bg-slate-50 p-4 rounded-lg border border-slate-200">
                        {summary}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Key Findings */}
                <div className="p-6 bg-white border border-slate-200 rounded-xl shadow-sm">
                  <h2 className="text-base font-bold text-slate-900 mb-4 pb-2 border-b border-slate-100">
                    Detailed Fraud Detection Alerts ({findings.length})
                  </h2>
                  <div className="space-y-3">
                    {findings.length > 0 ? (
                      findings.map((f: any, i: number) => (
                        <FindingCard key={i} {...f} />
                      ))
                    ) : (
                      <div className="p-4 bg-green-50 border border-green-200 text-green-800 rounded-lg text-sm font-semibold flex items-center gap-2">
                        <CheckCircle2 className="w-5 h-5 text-green-600" />
                        No risk findings detected. Document structure and layout are safe.
                      </div>
                    )}
                  </div>
                </div>

                {/* Recommendations */}
                <div className="p-6 bg-white border border-slate-200 rounded-xl shadow-sm">
                  <h2 className="text-base font-bold text-slate-900 mb-4 pb-2 border-b border-slate-100">
                    Required Corrective Actions
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {recommendations.map((rec: string, i: number) => (
                      <div key={i} className="flex items-center gap-3 p-3.5 rounded-lg bg-blue-50 border border-blue-200">
                        <CheckCircle className="w-5 h-5 text-blue-600 flex-shrink-0" />
                        <span className="text-sm font-semibold text-blue-900">{rec}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'fields' && (
              <div className="space-y-6 animate-fade-in">
                {/* Extracted Fields */}
                <div className="p-6 bg-white border border-slate-200 rounded-xl shadow-sm">
                  <h2 className="text-base font-bold text-slate-900 mb-4 pb-2 border-b border-slate-100">
                    OCR Extracted Fields vs Source Documents
                  </h2>
                  <div className="overflow-x-auto border border-slate-200 rounded-lg">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 border-b border-slate-200">
                        <tr>
                          <th className="px-4 py-3 text-left font-semibold text-slate-900">Field</th>
                          <th className="px-4 py-3 text-left font-semibold text-slate-900">Extracted Value</th>
                          <th className="px-4 py-3 text-left font-semibold text-slate-900">Extraction Method</th>
                          <th className="px-4 py-3 text-left font-semibold text-slate-900">Confidence</th>
                          <th className="px-4 py-3 text-left font-semibold text-slate-900">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {extractedFields.map((f: any, i: number) => (
                          <FieldTableRow key={i} {...f} />
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Cross Document Checks */}
                <div className="p-6 bg-white border border-slate-200 rounded-xl shadow-sm">
                  <h2 className="text-base font-bold text-slate-900 mb-4 pb-2 border-b border-slate-100">
                    Cross-Document Mismatch Matrix
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {crossDocChecks.map((check: any, i: number) => (
                      <div
                        key={i}
                        className={`p-3 rounded-lg border ${
                          check.status === 'Match'
                            ? 'bg-green-50 border-green-200 text-green-900'
                            : 'bg-red-50 border-red-200 text-red-900'
                        }`}
                      >
                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">
                          {check.document} — {check.field}
                        </div>
                        <div className="text-sm font-bold flex items-center gap-2">
                          {check.status === 'Match' ? (
                            <CheckCircle2 className="w-4 h-4 text-green-600" />
                          ) : (
                            <AlertCircle className="w-4 h-4 text-red-600" />
                          )}
                          {check.status}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'registry' && (
              <div className="space-y-6 animate-fade-in">
                {/* Registry Verification */}
                <div className="p-6 bg-white border border-slate-200 rounded-xl shadow-sm">
                  <h2 className="text-base font-bold text-slate-900 mb-4 pb-2 border-b border-slate-100">
                    National Database & Registry Checks
                  </h2>
                  <div className="space-y-4">
                    {registryVerification.map((reg: any, i: number) => (
                      <div key={i} className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between">
                        <div>
                          <h4 className="font-bold text-sm text-slate-900">{reg.name} Verification</h4>
                          <p className="text-xs text-slate-505 mt-1">{reg.explanation}</p>
                        </div>
                        <span
                          className={`text-xs font-bold px-3 py-1 rounded-full ${
                            reg.status === 'Verified'
                              ? 'bg-green-100 text-green-700 border border-green-200'
                              : 'bg-red-100 text-red-700 border border-red-200'
                          }`}
                        >
                          {reg.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'documents' && (
              <div className="space-y-6 animate-fade-in">
                {/* Inspected Documents */}
                <div className="p-6 bg-white border border-slate-200 rounded-xl shadow-sm">
                  <h2 className="text-base font-bold text-slate-900 mb-4 pb-2 border-b border-slate-100">
                    File Audit & Metadata Inspection
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                    {documents.map((doc: any, i: number) => (
                      <div key={i} className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex flex-col justify-between">
                        <div>
                          <h4 className="font-bold text-sm text-slate-950 truncate">{doc.name}</h4>
                          <span className="inline-block mt-1 px-2.5 py-0.5 bg-blue-100 text-blue-700 text-[10px] font-bold rounded-full">
                            Type: {doc.type}
                          </span>
                        </div>
                        <div className="mt-4 pt-3 border-t border-slate-200 flex justify-between text-xs text-slate-500">
                          <span>Pages: {doc.pages}</span>
                          <span>OCR Done: {doc.pages_ocrd}</span>
                        </div>
                      </div>
                    ))}
                  </div>

                  {realData?.pages && realData.pages.length > 0 && (
                    <div>
                      <h3 className="text-sm font-bold text-slate-900 mb-4 pb-2 border-b border-slate-100">
                        Sanitized CDR Page Previews (Flat Pixels)
                      </h3>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {realData.pages.map((imgB64: string, idx: number) => (
                          <div key={idx} className="border border-slate-200 rounded-xl overflow-hidden shadow-sm bg-slate-50 p-2 flex flex-col items-center">
                            <div className="text-xs text-slate-500 font-bold mb-2">Page {idx + 1}</div>
                            <img
                              src={`data:image/png;base64,${imgB64}`}
                              alt={`Page ${idx + 1}`}
                              className="max-h-96 object-contain rounded border border-slate-300"
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Right Pane (Gauge, Underwriting decision inputs) */}
          <div className="lg:col-span-1 space-y-6">
            <div className="sticky top-24 space-y-6">
              <FraudGauge score={fraudScore} recommendedAction={recommendedAction} />

              {/* Manager Actions Card */}
              <div className="p-6 bg-white border border-slate-200 rounded-xl shadow-sm">
                <h3 className="text-sm font-bold text-slate-900 mb-4 uppercase tracking-wider pb-2 border-b border-slate-100">
                  Underwriter Decision Panel
                </h3>
                {decision ? (
                  <div className={`p-4 rounded-lg text-center ${
                    decision === 'Approved'
                      ? 'bg-green-50 border border-green-200 text-green-800'
                      : decision === 'Rejected'
                        ? 'bg-red-50 border border-red-200 text-red-800'
                        : 'bg-yellow-50 border border-yellow-250 text-yellow-800'
                  }`}>
                    <p className="text-xs font-semibold uppercase tracking-wider">Action Taken</p>
                    <p className="text-lg font-bold mt-1">{decision}</p>
                    {managerNote && (
                      <p className="text-xs text-slate-605 mt-2 italic">"{managerNote}"</p>
                    )}
                    <button
                      onClick={() => {
                        setDecision(null)
                        setManagerNote('')
                      }}
                      className="mt-4 text-xs font-semibold text-blue-600 hover:underline"
                    >
                      Reset Decision
                    </button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
                        Underwriting Manager Notes
                      </label>
                      <textarea
                        value={managerNote}
                        onChange={(e) => setManagerNote(e.target.value)}
                        placeholder="Provide details regarding the underwriting decision..."
                        className="w-full p-3 text-sm bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:border-blue-500 h-24 resize-none"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <button
                        onClick={() => {
                          if (!managerNote.trim()) {
                            alert('Please write manager notes first!')
                            return
                          }
                          setDecision('Approved')
                        }}
                        className="px-4 py-2.5 bg-green-55 text-white rounded-lg font-bold text-xs hover:bg-green-600 transition-colors shadow-sm"
                      >
                        Approve Loan
                      </button>
                      <button
                        onClick={() => {
                          if (!managerNote.trim()) {
                            alert('Please write manager notes first!')
                            return
                          }
                          setDecision('Rejected')
                        }}
                        className="px-4 py-2.5 bg-red-500 text-white rounded-lg font-bold text-xs hover:bg-red-600 transition-colors shadow-sm"
                      >
                        Reject Loan
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}