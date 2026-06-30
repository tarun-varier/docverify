import { createFileRoute, Link, useNavigate, useParams } from "@tanstack/react-router";
import { AppShell, Card, PageTitle } from "@/components/app-shell";
import { getCase, saveCase, addDocToCase } from "@/lib/mock-data";
import { UploadCloud, FileText, X, Building2, Scale, Wallet, AlertCircle } from "lucide-react";
import { useState, useRef } from "react";

export const Route = createFileRoute("/cases/$caseId/upload")({
  head: () => ({ meta: [{ title: "Document Upload · DocVerify" }] }),
  component: UploadPage,
});

type Cat = "land" | "legal" | "financial";
const cats: { id: Cat; title: string; subtitle: string; Icon: typeof Building2 }[] = [
  { id: "land", title: "Land Records & Property", subtitle: "Deeds, survey docs, registration", Icon: Building2 },
  { id: "legal", title: "Legal & Identity Documents", subtitle: "ID proofs, application, NOC", Icon: Scale },
  { id: "financial", title: "Financial Statements", subtitle: "Salary slips, bank statements, ITR", Icon: Wallet },
];

const API_BASE_URL = (() => {
  const configuredUrl = import.meta.env.VITE_API_URL ?? import.meta.env.VITE_BACKEND_URL;
  if (configuredUrl) {
    return configuredUrl.replace(/\/$/, '');
  }
  if (typeof window !== 'undefined' && window.location.hostname) {
    const host = window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname;
    return `${window.location.protocol}//${host}:8000`;
  }
  return 'http://127.0.0.1:8000';
})();

function formatFileSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

function UploadPage() {
  const { caseId } = useParams({ from: "/cases/$caseId/upload" });
  const navigate = useNavigate();
  const c = getCase(caseId);

  const [files, setFiles] = useState<Record<Cat, { name: string; size: string; status?: 'uploading' | 'done' | 'error' }[]>>(() => {
    if (caseId === "3G327H") {
      return {
        land: [{ name: "Property_Deed_2019.pdf", size: "1.8 MB", status: 'done' }],
        legal: [
          { name: "PAN_Card.jpg", size: "420 KB", status: 'done' },
          { name: "Application_Form_Signed.pdf", size: "612 KB", status: 'done' },
        ],
        financial: [
          { name: "Salary_Slip_Oct.pdf", size: "240 KB", status: 'done' },
          { name: "Bank_Statement_6mo.pdf", size: "2.1 MB", status: 'done' },
        ],
      };
    }
    if (c && c.docs) {
      const docsMap: Record<Cat, { name: string; size: string; status?: 'uploading' | 'done' | 'error' }[]> = {
        land: [],
        legal: [],
        financial: [],
      };
      c.docs.forEach((doc) => {
        docsMap[doc.category].push({ name: doc.name, size: doc.size, status: 'done' });
      });
      return docsMap;
    }
    return { land: [], legal: [], financial: [] };
  });

  const [uploadingCat, setUploadingCat] = useState<Cat | null>(null);
  const [errorInfo, setErrorInfo] = useState<any>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeCatRef = useRef<Cat | null>(null);

  const totalFiles = Object.values(files).reduce((n, arr) => n + arr.length, 0);

  const handleZoneClick = (cat: Cat) => {
    activeCatRef.current = cat;
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    const cat = activeCatRef.current;
    if (!file || !cat) return;

    setErrorInfo(null);
    setUploadingCat(cat);

    // Add temporary file entry
    const newEntry = { name: file.name, size: formatFileSize(file.size), status: 'uploading' as const };
    setFiles(prev => ({
      ...prev,
      [cat]: [...prev[cat], newEntry]
    }));

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      const payload = await res.json().catch(() => null);

      if (!res.ok) {
        // Remove the temporary file entry
        setFiles(prev => ({
          ...prev,
          [cat]: prev[cat].filter(f => f.name !== file.name)
        }));

        if (payload && payload.detail) {
          setErrorInfo(payload.detail);
        } else {
          setErrorInfo("Security Gateway or Backend returned an upload error.");
        }
        return;
      }

      // Upload succeeded! Update dynamic case state
      addDocToCase(caseId, file.name, formatFileSize(file.size), payload, cat);

      // Set status to done
      setFiles(prev => ({
        ...prev,
        [cat]: prev[cat].map(f => f.name === file.name ? { ...f, status: 'done' } : f)
      }));

    } catch (err) {
      setFiles(prev => ({
        ...prev,
        [cat]: prev[cat].filter(f => f.name !== file.name)
      }));
      setErrorInfo(err instanceof Error ? err.message : "Unable to communicate with backend.");
    } finally {
      setUploadingCat(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const remove = (cat: Cat, i: number) => {
    const fileToRemove = files[cat][i];
    setFiles({ ...files, [cat]: files[cat].filter((_, idx) => idx !== i) });
    if (c) {
      c.docs = c.docs.filter((d) => !(d.name === fileToRemove.name && d.category === cat));
      c.score = Math.max(...c.docs.map((d) => d.subScore), 0);
      saveCase(c);
    }
  };

  return (
    <AppShell>
      <CaseBar
        applicant={c?.applicant ?? "Jeff Henry"}
        caseId={caseId}
        amount={c?.loanAmount ?? 4500000}
      />
      <PageTitle title="Document Upload" subtitle="More documents enable richer cross-document checks." />

      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        className="hidden"
        accept=".pdf"
      />

      {errorInfo && (
        <div className="mb-6 rounded-xl border border-destructive/35 bg-destructive/10 p-5 text-[var(--risk-critical)] shadow-sm animate-fade-in text-left">
          {typeof errorInfo === 'object' ? (
            <div>
              <div className="flex items-center justify-between border-b border-destructive/20 pb-3 mb-3">
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-1 rounded-md bg-destructive/20 text-destructive text-xs font-extrabold tracking-wider uppercase border border-destructive/30">
                    {errorInfo.status || 'REJECTED'}
                  </span>
                  <span className="text-xs font-bold text-destructive uppercase tracking-wide">
                    Threat Level: {errorInfo.threat || 'HIGH'}
                  </span>
                </div>
                <span className="text-xs text-destructive/80 font-mono">Layer 0 Gateway Block</span>
              </div>
              <p className="text-sm font-bold text-destructive mb-2">Layer 0 Security Gateway Blocked This Document:</p>
              <ul className="list-disc list-inside space-y-1 text-xs text-destructive font-mono bg-white/70 p-3 rounded-lg border border-destructive/20">
                {errorInfo.findings && errorInfo.findings.length > 0 ? (
                  errorInfo.findings.map((f: string, idx: number) => <li key={idx}>{f}</li>)
                ) : (
                  <li>{errorInfo.detail || 'Suspicious or corrupted PDF structure detected.'}</li>
                )}
              </ul>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <AlertCircle className="size-5 text-destructive shrink-0" />
              <span className="text-sm font-medium">{errorInfo}</span>
            </div>
          )}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        {cats.map((cat) => (
          <Card key={cat.id} className="flex flex-col">
            <div className="border-b border-border p-5">
              <div className="flex items-center gap-3">
                <div className="grid size-10 place-items-center rounded-lg bg-primary-soft text-[var(--accent-foreground)]">
                  <cat.Icon className="size-5" />
                </div>
                <div>
                  <div className="font-semibold">{cat.title}</div>
                  <div className="text-xs text-muted-foreground">{cat.subtitle}</div>
                </div>
              </div>
            </div>
            <div className="p-5 space-y-3 flex-1 flex flex-col justify-between">
              <button
                onClick={() => handleZoneClick(cat.id)}
                disabled={uploadingCat !== null}
                className="flex w-full flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-border bg-background px-4 py-8 text-center hover:border-primary hover:bg-primary-soft/40 disabled:opacity-50 cursor-pointer"
              >
                <UploadCloud className="size-6 text-primary" />
                <div className="text-sm font-medium">Drop file or click to browse</div>
                <div className="text-xs text-muted-foreground">PDF only · up to 10 MB</div>
              </button>
              <div className="space-y-2 mt-4">
                {files[cat.id].map((f, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-2">
                    <FileText className="size-4 text-primary shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm">{f.name}</div>
                      <div className="text-[11px] text-muted-foreground">{f.size} · {f.status === 'uploading' ? 'Uploading...' : 'Uploaded'}</div>
                      <div className="mt-1 h-1 rounded-full bg-secondary">
                        <div 
                          className={`h-1 rounded-full ${f.status === 'uploading' ? 'bg-primary animate-pulse' : 'bg-[var(--success)]'}`} 
                          style={{ width: "100%" }} 
                        />
                      </div>
                    </div>
                    <button onClick={() => remove(cat.id, i)} className="text-muted-foreground hover:text-destructive cursor-pointer">
                      <X className="size-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <Link to="/cases/new" className="rounded-lg border border-border bg-surface px-4 py-2.5 text-sm">
          Back to case details
        </Link>
        <div className="flex items-center gap-3">
          <div className="text-xs text-muted-foreground">{totalFiles} files attached</div>
          <button
            disabled={totalFiles === 0}
            onClick={() => navigate({ to: "/cases/$caseId/analyzing", params: { caseId } })}
            className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50 cursor-pointer"
          >
            Run Analysis
          </button>
        </div>
      </div>
    </AppShell>
  );
}

export function CaseBar({ applicant, caseId, amount, extra }: { applicant: string; caseId: string; amount: number; extra?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface px-5 py-3">
      <div className="flex items-center gap-4">
        <div className="grid size-10 place-items-center rounded-full bg-primary-soft text-[var(--accent-foreground)] font-semibold">
          {applicant.split(" ").map((p) => p[0]).slice(0, 2).join("")}
        </div>
        <div>
          <div className="font-semibold">{applicant}</div>
          <div className="text-xs text-muted-foreground">Case #{caseId} · ₹{amount.toLocaleString("en-IN")}</div>
        </div>
      </div>
      {extra}
    </div>
  );
}