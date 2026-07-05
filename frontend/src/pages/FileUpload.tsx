import { type ChangeEvent, type DragEvent, type KeyboardEvent, useMemo, useRef, useState } from 'react'
import ResultsDashboard, { type CaseResult } from '../components/ResultsDashboard'

type SecurityFinding = {
	status?: string
	threat?: string
	findings?: string[]
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

function isCaseResult(payload: unknown): payload is CaseResult {
	return (
		typeof payload === 'object' &&
		payload !== null &&
		'case_id' in payload &&
		'fraud_score' in payload &&
		'documents' in payload
	)
}

export default function FileUpload() {
	const [selectedFile, setSelectedFile] = useState<File | null>(null)
	const [isDragging, setIsDragging] = useState(false)
	const [isUploading, setIsUploading] = useState(false)
	const [uploadProgress, setUploadProgress] = useState('')
	const [errorInfo, setErrorInfo] = useState<SecurityFinding | string | null>(null)
	const [caseResult, setCaseResult] = useState<CaseResult | null>(null)

	const fileInputRef = useRef<HTMLInputElement>(null)

	const fileDetails = useMemo(() => {
		if (!selectedFile) {
			return null
		}

		return {
			name: selectedFile.name,
			size: `${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB`,
			type: selectedFile.type || 'Unknown type',
		}
	}, [selectedFile])

	const openPicker = () => {
		fileInputRef.current?.click()
	}

	const selectFile = (file: File | null) => {
		if (!file) {
			return
		}

		setSelectedFile(file)
		setErrorInfo(null)
		setCaseResult(null)
	}

	const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
		selectFile(event.target.files?.[0] ?? null)
	}

	const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
		event.preventDefault()
		setIsDragging(true)
	}

	const handleDragLeave = () => {
		setIsDragging(false)
	}

	const handleDrop = (event: DragEvent<HTMLDivElement>) => {
		event.preventDefault()
		setIsDragging(false)
		selectFile(event.dataTransfer.files?.[0] ?? null)
	}

	const handleReset = () => {
		setSelectedFile(null)
		setCaseResult(null)
		setErrorInfo(null)
		setUploadProgress('')
		if (fileInputRef.current) {
			fileInputRef.current.value = ''
		}
	}

	const handleUpload = async () => {
		if (!selectedFile) {
			setErrorInfo('Choose a file before uploading.')
			return
		}

		const formData = new FormData()
		formData.append('file', selectedFile)

		setIsUploading(true)
		setErrorInfo(null)
		setCaseResult(null)
		setUploadProgress('Sending to security sandbox…')

		try {
			const result = await fetch(`${API_BASE_URL}/upload`, {
				method: 'POST',
				body: formData,
			})

			setUploadProgress('Processing response…')
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

			// Check if this is a full CaseResult from the pipeline
			if (isCaseResult(payload)) {
				setCaseResult(payload as CaseResult)
			} else {
				// Sandbox-only response (shouldn't happen after our changes, but handle gracefully)
				setErrorInfo('Received an unexpected response format from the server.')
			}
		} catch (uploadError) {
			const msg = uploadError instanceof Error ? uploadError.message : 'Unable to communicate with backend.'
			setErrorInfo(msg)
		} finally {
			setIsUploading(false)
			setUploadProgress('')
		}
	}

	// If we have a CaseResult, show the dashboard
	if (caseResult) {
		return (
			<main className="min-h-screen bg-slate-950 text-slate-100 p-6 font-sans">
				<div style={{ maxWidth: '56rem', margin: '0 auto' }}>
					<ResultsDashboard result={caseResult} onReset={handleReset} />
				</div>
			</main>
		)
	}

	// Otherwise show the upload form
	return (
		<main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6 font-sans">
			<section className="w-full max-w-2xl rounded-3xl border border-slate-800 bg-slate-900/40 p-8 shadow-2xl backdrop-blur-md">
				<div className="flex items-start justify-between gap-4 mb-6">
					<div>
						<p className="text-xs uppercase tracking-widest text-indigo-400 font-bold">DocVerify AI</p>
						<h1 className="text-3xl font-extrabold tracking-tight mt-1 text-slate-100">Document Verification</h1>
						<p className="text-sm text-slate-400 mt-2">Upload a document to run security scanning & multi-layer fraud analysis.</p>
					</div>
					<div className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 text-xs font-semibold text-emerald-400 flex items-center gap-2">
						<span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
						Pipeline Active
					</div>
				</div>

				<input
					ref={fileInputRef}
					type="file"
					accept=".pdf"
					className="hidden"
					onChange={handleFileChange}
				/>

				<div
					role="button"
					tabIndex={0}
					onClick={openPicker}
					onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => {
						if (event.key === 'Enter' || event.key === ' ') {
							event.preventDefault()
							openPicker()
						}
					}}
					onDragOver={handleDragOver}
					onDragLeave={handleDragLeave}
					onDrop={handleDrop}
					className={`rounded-3xl border-2 border-dashed p-8 text-center transition-all duration-300 ${isDragging ? 'border-indigo-400 bg-indigo-500/10' : 'border-slate-800 bg-slate-950/40 hover:border-slate-600 hover:bg-slate-900/30'}`}
				>
					<div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-8 w-8">
							<path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0-4 4m4-4 4 4M4 16.5A2.5 2.5 0 0 1 6.5 14h11a2.5 2.5 0 0 1 2.5 2.5v1a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5v-1Z" />
						</svg>
					</div>
					<h2 className="mt-4 text-xl font-bold">Drag and drop your PDF here</h2>
					<p className="mt-2 text-sm text-slate-400">Or click to browse from your device.</p>
				</div>

				<div className="mt-6 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
					<div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
						<div className="min-w-0">
							<p className="text-xs font-bold uppercase tracking-wider text-slate-400">Selected File</p>
							{fileDetails ? (
								<div className="mt-1 text-sm text-slate-300">
									<p className="truncate font-semibold text-slate-100">{fileDetails.name}</p>
									<p className="text-xs text-slate-400 mt-0.5">{fileDetails.size} • {fileDetails.type}</p>
								</div>
							) : (
								<p className="mt-1 text-sm text-slate-500">No file selected yet.</p>
							)}
						</div>

						<button
							type="button"
							onClick={handleUpload}
							disabled={!selectedFile || isUploading}
							className="rounded-xl bg-indigo-600 hover:bg-indigo-500 px-6 py-3 text-sm font-bold text-white transition-all shadow-lg shadow-indigo-600/20 disabled:cursor-not-allowed disabled:opacity-50"
						>
							{isUploading ? 'Analyzing…' : 'Scan & Analyze'}
						</button>
					</div>
				</div>

				{/* Upload progress indicator */}
				{isUploading && uploadProgress && (
					<div className="mt-4 rounded-2xl border border-indigo-500/20 bg-indigo-500/5 p-4 animate-fade-in">
						<div className="flex items-center gap-3">
							<div className="upload-spinner" />
							<div>
								<p className="text-sm font-semibold text-indigo-300">{uploadProgress}</p>
								<p className="text-xs text-slate-400 mt-0.5">This may take a moment for large documents…</p>
							</div>
						</div>
						<div className="upload-progress-bar mt-3">
							<div className="upload-progress-bar__fill" />
						</div>
					</div>
				)}

				{/* Structured Security Error / Rejection Card */}
				{errorInfo && (
					<div className="mt-6 rounded-2xl border border-red-500/30 bg-red-500/10 p-5 text-red-200 shadow-xl animate-fade-in">
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
									<span className="text-xs text-red-400/80 font-mono">Security Gateway Block</span>
								</div>
								<p className="text-sm font-bold text-red-100 mb-2">Security Gateway Blocked This Document:</p>
								<ul className="list-disc list-inside space-y-1 text-sm text-red-300/90 font-mono bg-slate-950/60 p-3 rounded-xl border border-red-500/20">
									{errorInfo.findings && errorInfo.findings.length > 0 ? (
										errorInfo.findings.map((f, i) => <li key={i}>{f}</li>)
									) : (
										<li>Suspicious or corrupted PDF structure detected.</li>
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
			</section>
		</main>
	)
}

