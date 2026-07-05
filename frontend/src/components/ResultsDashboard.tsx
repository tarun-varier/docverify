import CircularProgress from './CircularProgress'

/* ─── Pipeline types (mirrors backend CaseResult) ─── */

export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical'

export type Anomaly = {
	code: string
	layer: string
	severity: Severity
	title: string
	detail: string
	documents: string[]
}

export type DocumentReport = {
	filename: string
	sha256: string
	doc_type: string
	page_count: number
	text_chars: number
	ocr_used: boolean
	fields: Record<string, unknown>
	metadata: Record<string, string>
	anomalies: Anomaly[]
	ela_image?: string | null
	suspicious_regions: Array<Record<string, number>>
}

export type LLMSummary = {
	executive_summary?: string
	key_findings?: string[]
	risk_analysis?: string
	recommended_actions?: string[]
	manual_review_required?: boolean
	underwriter_notes?: string
}

export type CaseResult = {
	case_id: string
	analyzed_at: string
	elapsed_seconds: number
	fraud_score: number
	risk_band: string
	recommended_action: string
	recommendations: string[]
	documents: DocumentReport[]
	cross_document_anomalies: Anomaly[]
	registry_anomalies: Anomaly[]
	llm_summary: LLMSummary
	audit_entry: Record<string, unknown>
	sandbox?: {
		status: string
		page_count?: number
		ml_prediction?: Record<string, unknown>
		request_id?: string
	}
}

/* ─── Helpers ─── */

const SEVERITY_CONFIG: Record<Severity, { label: string; className: string; dotClass: string }> = {
	info: { label: 'INFO', className: 'severity-badge severity-info', dotClass: 'severity-dot severity-dot--info' },
	low: { label: 'LOW', className: 'severity-badge severity-low', dotClass: 'severity-dot severity-dot--low' },
	medium: { label: 'MEDIUM', className: 'severity-badge severity-medium', dotClass: 'severity-dot severity-dot--medium' },
	high: { label: 'HIGH', className: 'severity-badge severity-high', dotClass: 'severity-dot severity-dot--high' },
	critical: { label: 'CRITICAL', className: 'severity-badge severity-critical', dotClass: 'severity-dot severity-dot--critical' },
}

const BAND_COLORS: Record<string, string> = {
	LOW: '#10b981',
	MEDIUM: '#f59e0b',
	HIGH: '#ef4444',
	CRITICAL: '#dc2626',
}

function formatDocType(t: string): string {
	return t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

/* ─── Sub-components ─── */

function SeverityBadge({ severity }: { severity: Severity }) {
	const cfg = SEVERITY_CONFIG[severity] ?? SEVERITY_CONFIG.info
	return (
		<span className={cfg.className}>
			<span className={cfg.dotClass} />
			{cfg.label}
		</span>
	)
}

function AnomalyCard({ anomaly }: { anomaly: Anomaly }) {
	return (
		<div className="anomaly-card animate-fade-in">
			<div className="anomaly-card__header">
				<SeverityBadge severity={anomaly.severity} />
				<span className="anomaly-card__code">{anomaly.code}</span>
			</div>
			<p className="anomaly-card__title">{anomaly.title}</p>
			<p className="anomaly-card__detail">{anomaly.detail}</p>
			{anomaly.documents.length > 0 && (
				<div className="anomaly-card__docs">
					{anomaly.documents.map((d, i) => (
						<span key={i} className="anomaly-card__doc-tag">{d}</span>
					))}
				</div>
			)}
		</div>
	)
}

function DocumentCard({ doc }: { doc: DocumentReport }) {
	return (
		<div className="doc-card animate-fade-in">
			<div className="doc-card__header">
				<div className="doc-card__icon">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
						<path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
					</svg>
				</div>
				<div className="doc-card__info">
					<p className="doc-card__filename">{doc.filename}</p>
					<p className="doc-card__meta">
						{formatDocType(doc.doc_type)} • {doc.page_count} page{doc.page_count !== 1 ? 's' : ''} • {doc.text_chars.toLocaleString()} chars
						{doc.ocr_used && <span className="doc-card__ocr-tag">OCR</span>}
					</p>
				</div>
			</div>

			{/* Fields summary */}
			{doc.fields && Object.keys(doc.fields).length > 0 && (
				<div className="doc-card__fields">
					{Object.entries(doc.fields as Record<string, unknown>)
						.filter(([key, val]) => val != null && val !== '' && key !== 'extraction_meta' && !Array.isArray(val))
						.slice(0, 6)
						.map(([key, val]) => (
							<div key={key} className="doc-card__field">
								<span className="doc-card__field-label">{key.replace(/_/g, ' ')}</span>
								<span className="doc-card__field-value">{String(val)}</span>
							</div>
						))}
				</div>
			)}

			{/* Per-document anomalies */}
			{doc.anomalies.length > 0 && (
				<div className="doc-card__anomalies">
					<p className="doc-card__anomalies-title">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
							<path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
						</svg>
						{doc.anomalies.length} Anomal{doc.anomalies.length === 1 ? 'y' : 'ies'}
					</p>
					{doc.anomalies.map((a, i) => (
						<AnomalyCard key={i} anomaly={a} />
					))}
				</div>
			)}

			{doc.anomalies.length === 0 && (
				<div className="doc-card__clean">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
						<path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
					</svg>
					No anomalies detected
				</div>
			)}
		</div>
	)
}

/* ─── Main Dashboard ─── */

export default function ResultsDashboard({ result, onReset }: { result: CaseResult; onReset: () => void }) {
	const bandColor = BAND_COLORS[result.risk_band] ?? '#64748b'
	const allAnomalies = [
		...result.documents.flatMap(d => d.anomalies),
		...result.cross_document_anomalies,
		...result.registry_anomalies,
	]
	const criticalCount = allAnomalies.filter(a => a.severity === 'critical' || a.severity === 'high').length

	return (
		<div className="dashboard animate-fade-in">
			{/* Top bar */}
			<div className="dashboard__top-bar">
				<div>
					<p className="dashboard__brand">DocVerify AI</p>
					<h1 className="dashboard__title">Analysis Report</h1>
				</div>
				<button type="button" onClick={onReset} className="dashboard__new-btn">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
						<path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
					</svg>
					New Scan
				</button>
			</div>

			{/* Case meta strip */}
			<div className="dashboard__meta-strip">
				<span className="dashboard__meta-item">
					<span className="dashboard__meta-label">Case</span>
					<span className="dashboard__meta-value font-mono">{result.case_id}</span>
				</span>
				<span className="dashboard__meta-item">
					<span className="dashboard__meta-label">Time</span>
					<span className="dashboard__meta-value">{result.elapsed_seconds}s</span>
				</span>
				<span className="dashboard__meta-item">
					<span className="dashboard__meta-label">Documents</span>
					<span className="dashboard__meta-value">{result.documents.length}</span>
				</span>
				<span className="dashboard__meta-item">
					<span className="dashboard__meta-label">Anomalies</span>
					<span className="dashboard__meta-value" style={{ color: criticalCount > 0 ? '#f87171' : '#34d399' }}>
						{allAnomalies.length}
					</span>
				</span>
			</div>

			{/* Fraud score hero */}
			<div className="dashboard__score-section">
				<div className="dashboard__score-gauge">
					<CircularProgress score={result.fraud_score} size={180} strokeWidth={12} riskLevel={result.risk_band} />
				</div>
				<div className="dashboard__score-info">
					<div className="dashboard__risk-badge" style={{ borderColor: `${bandColor}44`, backgroundColor: `${bandColor}15`, color: bandColor }}>
						<span className="dashboard__risk-dot" style={{ backgroundColor: bandColor }} />
						{result.risk_band} RISK
					</div>
					<p className="dashboard__action">{result.recommended_action}</p>
					{result.recommendations.length > 0 && (
						<ul className="dashboard__recommendations">
							{result.recommendations.map((r, i) => (
								<li key={i}>{r}</li>
							))}
						</ul>
					)}
				</div>
			</div>

			{/* LLM Underwriting Summary */}
			{result.llm_summary?.executive_summary && (
				<div className="dashboard__section">
					<h2 className="dashboard__section-title">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
							<path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
						</svg>
						AI Underwriting Summary
					</h2>
					<div className="dashboard__llm-card">
						<p className="dashboard__llm-summary">{result.llm_summary.executive_summary}</p>

						{result.llm_summary.key_findings && result.llm_summary.key_findings.length > 0 && (
							<div className="dashboard__llm-findings">
								<p className="dashboard__llm-findings-title">Key Findings</p>
								<ul>
									{result.llm_summary.key_findings.map((f, i) => (
										<li key={i}>{f}</li>
									))}
								</ul>
							</div>
						)}

						{result.llm_summary.risk_analysis && (
							<div className="dashboard__llm-risk">
								<p className="dashboard__llm-findings-title">Risk Analysis</p>
								<p>{result.llm_summary.risk_analysis}</p>
							</div>
						)}

						{result.llm_summary.manual_review_required && (
							<div className="dashboard__manual-review">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
									<path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
								</svg>
								Manual review required
							</div>
						)}
					</div>
				</div>
			)}

			{/* Document reports */}
			<div className="dashboard__section">
				<h2 className="dashboard__section-title">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
						<path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
					</svg>
					Document Analysis
				</h2>
				{result.documents.map((doc, i) => (
					<DocumentCard key={i} doc={doc} />
				))}
			</div>

			{/* Cross-document anomalies */}
			{result.cross_document_anomalies.length > 0 && (
				<div className="dashboard__section">
					<h2 className="dashboard__section-title">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
							<path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
						</svg>
						Cross-Document Anomalies
					</h2>
					{result.cross_document_anomalies.map((a, i) => (
						<AnomalyCard key={i} anomaly={a} />
					))}
				</div>
			)}

			{/* Registry anomalies */}
			{result.registry_anomalies.length > 0 && (
				<div className="dashboard__section">
					<h2 className="dashboard__section-title">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
							<path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
						</svg>
						Registry Anomalies
					</h2>
					{result.registry_anomalies.map((a, i) => (
						<AnomalyCard key={i} anomaly={a} />
					))}
				</div>
			)}

			{/* Audit footer */}
			<div className="dashboard__footer">
				<span>Analyzed at {new Date(result.analyzed_at).toLocaleString()}</span>
				<span className="font-mono">SHA: {result.documents[0]?.sha256.slice(0, 12)}…</span>
			</div>
		</div>
	)
}
