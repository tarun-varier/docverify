import './App.css'
import FileUpload from './pages/FileUpload'

export default function App() {
  return <FileUpload />
}
/*
import './App.css'
import FileUpload from './pages/FileUpload'

export default function App() {
  return <FileUpload />
}import React, { useState, useEffect, useRef } from 'react';
import CircularProgress from './components/CircularProgress';
import './App.css';

interface Finding {
  type: string;
  severity: 'danger' | 'warning' | 'info';
  message: string;
}

interface ScanReport {
  file_name: string;
  file_size: number;
  pages: number;
  metadata: Record<string, string>;
  threat_score: number;
  risk_level: string;
  findings: Finding[];
  keywords_detected: Record<string, number>;
  extracted_links: { page: number | string; url: string }[];
  structure: {
    has_javascript: boolean;
    has_openaction: boolean;
    has_launch: boolean;
    has_embedded_file: boolean;
    has_xfa: boolean;
  };
}

const SCAN_STEPS = [
  "Initializing local sandbox environment...",
  "Reading raw binary stream offsets...",
  "Analyzing PDF dictionary keys and objects...",
  "Scanning stream encodings for script payloads...",
  "Inspecting document actions for automatic triggers (/OpenAction, /AA)...",
  "Checking for hidden embedded executable attachments...",
  "Running heuristic scoring rules...",
  "Finalizing analysis report..."
];

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [scanning, setScanning] = useState<boolean>(false);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [stepLogs, setStepLogs] = useState<string[]>([]);
  const [report, setReport] = useState<ScanReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Helper to format bytes
  const formatBytes = (bytes: number, decimals = 2) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.type === 'application/pdf') {
      processFile(droppedFile);
    } else {
      setError("Please upload a valid PDF file.");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      processFile(selectedFile);
    }
  };

  const processFile = async (selectedFile: File) => {
    setFile(selectedFile);
    setError(null);
    setReport(null);
    setScanning(true);
    setCurrentStep(0);
    setStepLogs([SCAN_STEPS[0]]);

    // Prepare upload
    const formData = new FormData();
    formData.append('file', selectedFile);

    // Trigger local scan concurrently with progress simulation
    try {
      const uploadPromise = fetch('http://localhost:8000/api/scan', {
        method: 'POST',
        body: formData,
      });

      // Simulate steps
      let stepIndex = 0;
      const stepInterval = setInterval(() => {
        if (stepIndex < SCAN_STEPS.length - 2) {
          stepIndex++;
          setCurrentStep(stepIndex);
          setStepLogs(prev => [...prev, SCAN_STEPS[stepIndex]]);
        }
      }, 350);

      // Wait for both steps to advance and backend to respond
      const response = await uploadPromise;
      clearInterval(stepInterval);

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Server error during scanning");
      }

      const scanResult: ScanReport = await response.json();

      // Finish logs fast
      for (let i = stepIndex + 1; i < SCAN_STEPS.length; i++) {
        setCurrentStep(i);
        setStepLogs(prev => [...prev, SCAN_STEPS[i]]);
        await new Promise(resolve => setTimeout(resolve, 150));
      }

      setTimeout(() => {
        setReport(scanResult);
        setScanning(false);
      }, 300);

    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to communicate with the local scan engine.");
      setScanning(false);
    }
  };

  const triggerBrowse = () => {
    fileInputRef.current?.click();
  };

  const resetScanner = () => {
    setFile(null);
    setReport(null);
    setError(null);
    setStepLogs([]);
  };

  // Get Risk Color Class
  const getRiskBadgeStyles = (level: string) => {
    switch (level.toLowerCase()) {
      case 'safe':
        return { bg: 'rgba(16, 185, 129, 0.1)', text: '#10b981', border: '1px solid rgba(16, 185, 129, 0.2)' };
      case 'low risk':
        return { bg: 'rgba(52, 211, 153, 0.1)', text: '#34d399', border: '1px solid rgba(52, 211, 153, 0.2)' };
      case 'suspicious':
        return { bg: 'rgba(245, 158, 11, 0.1)', text: '#f59e0b', border: '1px solid rgba(245, 158, 11, 0.2)' };
      case 'dangerous':
        return { bg: 'rgba(239, 68, 68, 0.1)', text: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)' };
      default:
        return { bg: 'rgba(148, 163, 184, 0.1)', text: '#94a3b8', border: '1px solid rgba(148, 163, 184, 0.2)' };
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      {/* Sleek Header * /}
      <header className="border-b border-slate-900 bg-slate-950/80 backdrop-blur sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-indigo-200 via-slate-100 to-purple-200 bg-clip-text text-transparent">
              DocVerify Sandbox
            </h1>
            <p className="text-xs text-slate-400">Local & Offline PDF Security Scanner</p>
          </div>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold shadow-inner">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          Local Engine Active
        </div>
      </header>

      {/* Main Body * /}
      <main className="flex-1 max-w-6xl w-full mx-auto p-6 md:p-8 flex flex-col justify-center">
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 flex items-center justify-between text-sm animate-fade-in">
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-200 font-semibold uppercase tracking-wider text-xs">
              Dismiss
            </button>
          </div>
        )}

        {/* State 1: Dropzone Uploader * /}
        {!file && !scanning && !report && (
          <div className="max-w-2xl w-full mx-auto text-center space-y-8 py-10">
            <div className="space-y-3">
              <h2 className="text-3xl font-extrabold tracking-tight text-slate-100 sm:text-4xl">
                Verify any PDF safely, locally.
              </h2>
              <p className="text-slate-400 text-base max-w-lg mx-auto leading-relaxed">
                Analyze document structures, check for hidden scripts, and flag execution triggers entirely in your browser-bound local sandbox.
              </p>
            </div>

            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={triggerBrowse}
              className={`border-2 border-dashed rounded-3xl p-12 flex flex-col items-center justify-center cursor-pointer transition-all duration-300 relative group overflow-hidden ${
                isDragOver
                  ? 'border-indigo-500 bg-indigo-500/5 shadow-2xl shadow-indigo-500/10'
                  : 'border-slate-800 hover:border-slate-700 bg-slate-900/20 hover:bg-slate-900/40'
              }`}
            >
              {/* Glow effects * /}
              <div className="absolute -inset-x-20 -inset-y-20 bg-indigo-500/5 blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
              
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={handleFileChange}
              />

              <div className="w-16 h-16 rounded-2xl bg-slate-950 border border-slate-850 flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-300 z-10">
                <svg className="w-8 h-8 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>

              <div className="mt-6 z-10">
                <p className="text-base font-semibold text-slate-200">
                  Drag and drop your PDF here, or <span className="text-indigo-400 hover:text-indigo-300">browse files</span>
                </p>
                <p className="text-xs text-slate-500 mt-2">
                  Supports .pdf files up to 50MB
                </p>
              </div>
            </div>

            <div className="flex items-center justify-center gap-8 pt-4 text-xs text-slate-500 border-t border-slate-900">
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-emerald-500/80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <span>Zero Internet Required</span>
              </div>
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-indigo-500/80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                <span>Static & Heuristic Sandbox Analysis</span>
              </div>
            </div>
          </div>
        )}

        {/* State 2: Active Scanning Log * /}
        {scanning && (
          <div className="max-w-xl w-full mx-auto space-y-8 py-10 animate-pulse-slow">
            <div className="text-center space-y-4">
              <div className="inline-flex items-center justify-center p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-2xl text-indigo-400">
                <svg className="w-8 h-8 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
              <h2 className="text-xl font-bold tracking-tight">Analyzing {file?.name}</h2>
              <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-indigo-500 h-full rounded-full transition-all duration-300"
                  style={{ width: `${((currentStep + 1) / SCAN_STEPS.length) * 100}%` }}
                />
              </div>
            </div>

            {/* Virtual Scanning Logs Console * /}
            <div className="bg-slate-950 border border-slate-900 rounded-2xl p-5 font-mono text-xs text-indigo-300/80 shadow-2xl relative overflow-hidden h-64 flex flex-col justify-end">
              <div className="absolute inset-x-0 top-0 h-8 bg-slate-950 border-b border-slate-900/50 px-4 flex items-center justify-between text-slate-500 select-none">
                <span>SANDBOX CONSOLE</span>
                <span>OFFLINE_SCAN_EXEC</span>
              </div>
              <div className="overflow-y-auto space-y-2 mt-4 pr-2 flex-1 scrollbar-thin">
                {stepLogs.map((log, index) => (
                  <div key={index} className="flex gap-3 items-start animate-fade-in">
                    <span className="text-slate-600 select-none">[{index}]</span>
                    {index === currentStep ? (
                      <span className="text-indigo-400 font-semibold flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-ping"></span>
                        {log}
                      </span>
                    ) : (
                      <span className="text-slate-400">{log} DONE</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* State 3: Detailed Report * /}
        {report && !scanning && (
          <div className="space-y-6 py-6 animate-fade-in">
            {/* Top Bar Actions * /}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-900 pb-4">
              <div>
                <span className="text-xs text-indigo-400 font-bold uppercase tracking-widest">Analysis Finished</span>
                <h2 className="text-2xl font-extrabold tracking-tight mt-0.5">{report.file_name}</h2>
              </div>
              <button
                onClick={resetScanner}
                className="self-start sm:self-center px-4 py-2 bg-slate-900 hover:bg-slate-850 border border-slate-800 text-slate-300 rounded-xl text-sm font-semibold hover:text-white transition-all shadow-md flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 8H17" />
                </svg>
                Scan Another File
              </button>
            </div>

            {/* Quick Threat Summary Cards * /}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Circular Gauge Card * /}
              <div className="bg-slate-900/30 border border-slate-900 rounded-3xl p-6 flex flex-col items-center justify-center text-center shadow-lg relative overflow-hidden">
                <div className="absolute top-4 left-4 text-xs text-slate-500 font-bold tracking-wider uppercase">Sandbox Assessment</div>
                <CircularProgress
                  score={report.threat_score}
                  riskLevel={report.risk_level}
                />
                
                {/* Risk Level Explanation badge * /}
                <div 
                  className="mt-5 px-3 py-1 rounded-full text-xs font-bold"
                  style={getRiskBadgeStyles(report.risk_level)}
                >
                  {report.risk_level}
                </div>
              </div>

              {/* File Core Stats Card * /}
              <div className="bg-slate-900/30 border border-slate-900 rounded-3xl p-6 flex flex-col justify-between shadow-lg relative overflow-hidden">
                <div className="text-xs text-slate-500 font-bold tracking-wider uppercase mb-4">File Details</div>
                <div className="space-y-4 flex-1 flex flex-col justify-center">
                  <div className="flex justify-between items-center border-b border-slate-900 pb-2">
                    <span className="text-slate-400 text-sm">File Size</span>
                    <span className="text-slate-200 font-mono font-medium">{formatBytes(report.file_size)}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-slate-900 pb-2">
                    <span className="text-slate-400 text-sm">Total Pages</span>
                    <span className="text-slate-200 font-mono font-medium">{report.pages} pages</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-slate-900 pb-2">
                    <span className="text-slate-400 text-sm">Threat Score</span>
                    <span className="text-slate-200 font-mono font-medium">{report.threat_score}/100</span>
                  </div>
                  <div className="flex justify-between items-center pb-1">
                    <span className="text-slate-400 text-sm">Integrity Status</span>
                    <span className="text-emerald-400 font-semibold">Ready</span>
                  </div>
                </div>
                <div className="text-xs text-slate-500 leading-relaxed mt-4 pt-3 border-t border-slate-900/40">
                  Static analysis scanned {formatBytes(report.file_size)} bytes and successfully evaluated PDF structures locally.
                </div>
              </div>

              {/* Detected Structural Flags Card * /}
              <div className="bg-slate-900/30 border border-slate-900 rounded-3xl p-6 flex flex-col justify-between shadow-lg relative overflow-hidden">
                <div className="text-xs text-slate-500 font-bold tracking-wider uppercase mb-4">Threat Elements (Raw Tags)</div>
                <div className="grid grid-cols-2 gap-3 flex-1 items-center">
                  <div className={`p-3 rounded-xl border flex flex-col ${report.structure.has_javascript ? 'bg-amber-500/5 border-amber-500/20 text-amber-400' : 'bg-slate-950/40 border-slate-900 text-slate-500'}`}>
                    <span className="text-xs uppercase font-bold tracking-wider">Scripts</span>
                    <span className="text-lg font-bold mt-1">{report.keywords_detected["/JavaScript"] || report.keywords_detected["/JS"] || 0} found</span>
                  </div>
                  <div className={`p-3 rounded-xl border flex flex-col ${report.structure.has_openaction ? 'bg-red-500/5 border-red-500/20 text-red-400' : 'bg-slate-950/40 border-slate-900 text-slate-500'}`}>
                    <span className="text-xs uppercase font-bold tracking-wider">Auto Run</span>
                    <span className="text-lg font-bold mt-1">{report.keywords_detected["/OpenAction"] || report.keywords_detected["/AA"] || 0} found</span>
                  </div>
                  <div className={`p-3 rounded-xl border flex flex-col ${report.structure.has_launch ? 'bg-red-500/5 border-red-500/30 text-red-400' : 'bg-slate-950/40 border-slate-900 text-slate-500'}`}>
                    <span className="text-xs uppercase font-bold tracking-wider">System Launch</span>
                    <span className="text-lg font-bold mt-1">{report.keywords_detected["/Launch"] || 0} found</span>
                  </div>
                  <div className={`p-3 rounded-xl border flex flex-col ${report.structure.has_embedded_file ? 'bg-amber-500/5 border-amber-500/20 text-amber-400' : 'bg-slate-950/40 border-slate-900 text-slate-500'}`}>
                    <span className="text-xs uppercase font-bold tracking-wider">Hidden Files</span>
                    <span className="text-lg font-bold mt-1">{report.keywords_detected["/EmbeddedFile"] || 0} found</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Detailed Warnings / Findings * /}
            {report.findings.length > 0 ? (
              <div className="space-y-3">
                <h3 className="text-base font-bold text-slate-300 uppercase tracking-wider">Sandbox Diagnostics ({report.findings.length})</h3>
                <div className="space-y-3">
                  {report.findings.map((finding, idx) => {
                    const isDanger = finding.severity === 'danger';
                    const isWarning = finding.severity === 'warning';
                    const iconColor = isDanger ? 'text-red-400' : isWarning ? 'text-amber-400' : 'text-blue-400';
                    const borderColor = isDanger ? 'border-red-500/20 bg-red-500/5' : isWarning ? 'border-amber-500/10 bg-amber-500/5' : 'border-slate-900 bg-slate-900/10';
                    
                    return (
                      <div key={idx} className={`p-4 rounded-2xl border flex gap-4 ${borderColor}`}>
                        <div className={`mt-0.5 shrink-0 ${iconColor}`}>
                          {isDanger ? (
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                          ) : (
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          )}
                        </div>
                        <div>
                          <p className={`text-sm font-semibold capitalize ${isDanger ? 'text-red-300' : isWarning ? 'text-amber-300' : 'text-slate-300'}`}>
                            {finding.type.replace('_', ' ')}
                          </p>
                          <p className="text-xs text-slate-400 mt-1 leading-relaxed">{finding.message}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="p-5 rounded-2xl border border-emerald-500/15 bg-emerald-500/5 flex gap-4 text-emerald-400/90 text-sm">
                <svg className="w-5 h-5 shrink-0 text-emerald-400 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <p className="font-semibold">Local Sandbox Status: Safe</p>
                  <p className="text-xs text-slate-400 mt-1">This PDF does not contain any suspicious executable elements, autostart triggers, or obfuscated blocks. It is safe to open in standard PDF viewers.</p>
                </div>
              </div>
            )}

            {/* Columns for Extracted URLs & Metadata * /}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Links list * /}
              <div className="bg-slate-900/20 border border-slate-900 rounded-3xl p-6 flex flex-col">
                <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center justify-between">
                  <span>Extracted Links ({report.extracted_links.length})</span>
                  <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </h3>
                {report.extracted_links.length > 0 ? (
                  <div className="flex-1 overflow-y-auto max-h-60 space-y-2 pr-2 scrollbar-thin">
                    {report.extracted_links.map((link, idx) => (
                      <div key={idx} className="p-3 bg-slate-950/60 border border-slate-900 rounded-xl flex items-center justify-between text-xs gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="text-slate-400 font-mono truncate">{link.url}</p>
                          <span className="text-[10px] text-slate-500">Found on page: {link.page}</span>
                        </div>
                        {/* Copy button * /}
                        <button
                          onClick={() => navigator.clipboard.writeText(link.url)}
                          className="shrink-0 px-2.5 py-1.5 bg-slate-900 border border-slate-805 hover:bg-indigo-500 hover:text-white rounded-lg text-slate-400 text-[10px] font-semibold transition-all"
                        >
                          Copy
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex-1 flex items-center justify-center text-slate-600 text-xs py-8">
                    No external URLs detected in document.
                  </div>
                )}
              </div>

              {/* Metadata list * /}
              <div className="bg-slate-900/20 border border-slate-900 rounded-3xl p-6 flex flex-col">
                <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center justify-between">
                  <span>Document Metadata</span>
                  <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </h3>
                {Object.keys(report.metadata).length > 0 ? (
                  <div className="flex-1 overflow-y-auto max-h-60 space-y-1.5 pr-2 scrollbar-thin">
                    {Object.entries(report.metadata).map(([key, val]) => (
                      <div key={key} className="flex justify-between items-center py-1.5 border-b border-slate-900 text-xs">
                        <span className="text-slate-500 font-semibold capitalize">{key.replace('_', ' ')}</span>
                        <span className="text-slate-300 font-mono text-right truncate max-w-[200px]" title={val}>{val}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex-1 flex items-center justify-center text-slate-600 text-xs py-8">
                    No document metadata keys detected.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer * /}
      <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-600 bg-slate-950 mt-10">
        <p>DocVerify Security Sandbox Engine v1.0.0 — 100% Offline Static & Heuristic Scan</p>
      </footer>
    </div>
  );
}
*/
