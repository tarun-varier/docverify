import { type ChangeEvent, type DragEvent, type KeyboardEvent, useMemo, useRef, useState } from 'react'

type UploadResponse = {
	message: string
	filename: string
	content_type: string | null
	size: number
}

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export default function FileUpload() {
	const [selectedFile, setSelectedFile] = useState<File | null>(null)
	const [isDragging, setIsDragging] = useState(false)
	const [isUploading, setIsUploading] = useState(false)
	const [error, setError] = useState<string | null>(null)
	const [response, setResponse] = useState<UploadResponse | null>(null)

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
		setError(null)
		setResponse(null)
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

	const handleUpload = async () => {
		if (!selectedFile) {
			setError('Choose a file before uploading.')
			return
		}

		const formData = new FormData()
		formData.append('file', selectedFile)

		setIsUploading(true)
		setError(null)
		setResponse(null)

		try {
			const result = await fetch(`${API_BASE_URL}/upload`, {
				method: 'POST',
				body: formData,
			})

			const payload = (await result.json().catch(() => null)) as UploadResponse | { detail?: string } | null

			if (!result.ok) {
				const message = payload && 'detail' in payload && payload.detail ? payload.detail : 'Upload failed.'
				throw new Error(message)
			}

			const uploadResponse = payload as UploadResponse | null
			setResponse({
				message: uploadResponse?.message ?? 'File uploaded successfully.',
				filename: uploadResponse?.filename ?? selectedFile.name,
				content_type: uploadResponse?.content_type ?? selectedFile.type ?? null,
				size: uploadResponse?.size ?? selectedFile.size,
			})
		} catch (uploadError) {
			const message = uploadError instanceof Error ? uploadError.message : 'Unable to upload the file.'
			setError(message)
		} finally {
			setIsUploading(false)
		}
	}

	return (
		<main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
			<section className="w-full max-w-2xl rounded-3xl border border-slate-800 bg-slate-900/30 p-6 shadow-2xl">
				<div className="flex items-start justify-between gap-4 mb-6">
					<div>
						<p className="text-xs uppercase tracking-widest text-indigo-300">DocVerify</p>
						<h1 className="text-3xl font-bold tracking-tight mt-1">Upload a file</h1>
						<p className="text-sm text-slate-400 mt-2">Choose a file, then send it to the backend at /upload.</p>
					</div>
					<div className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 text-xs font-semibold text-emerald-400">
						Backend Ready
					</div>
				</div>

				<input
					ref={fileInputRef}
					type="file"
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
					className={`rounded-3xl border-2 border-dashed p-8 text-center transition-colors ${isDragging ? 'border-indigo-400 bg-indigo-500/10' : 'border-slate-700 bg-slate-950/40 hover:border-slate-500'}`}
				>
					<div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-300">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-8 w-8">
							<path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0-4 4m4-4 4 4M4 16.5A2.5 2.5 0 0 1 6.5 14h11a2.5 2.5 0 0 1 2.5 2.5v1a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5v-1Z" />
						</svg>
					</div>
					<h2 className="mt-4 text-xl font-semibold">Drag and drop your file here</h2>
					<p className="mt-2 text-sm text-slate-400">Or click to browse from your device.</p>
				</div>

				<div className="mt-6 rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
					<div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
						<div className="min-w-0">
							<p className="text-sm font-semibold text-slate-200">Selected file</p>
							{fileDetails ? (
								<div className="mt-1 space-y-1 text-sm text-slate-400">
									<p className="truncate text-slate-100">{fileDetails.name}</p>
									<p>{fileDetails.size} • {fileDetails.type}</p>
								</div>
							) : (
								<p className="mt-1 text-sm text-slate-500">No file selected yet.</p>
							)}
						</div>

						<button
							type="button"
							onClick={handleUpload}
							disabled={!selectedFile || isUploading}
							className="rounded-xl bg-indigo-500 px-5 py-3 text-sm font-semibold text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
						>
							{isUploading ? 'Uploading…' : 'Upload file'}
						</button>
					</div>
				</div>

				{error && (
					<div className="mt-4 rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-200">
						{error}
					</div>
				)}

				{response && (
					<div className="mt-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-sm text-emerald-100">
						<p className="font-semibold">{response.message}</p>
						<div className="mt-2 grid gap-1 text-emerald-200 sm:grid-cols-3">
							<span>Name: {response.filename}</span>
							<span>Size: {(response.size / (1024 * 1024)).toFixed(2)} MB</span>
							<span>Type: {response.content_type ?? 'Unknown'}</span>
						</div>
					</div>
				)}
			</section>
		</main>
	)
}
