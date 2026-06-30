import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { AppShell, Card, RiskPill } from "@/components/app-shell";
import { CaseBar } from "./cases.$caseId.upload";
import { getCase, riskLabel } from "@/lib/mock-data";
import { ChevronLeft, ChevronRight, Eye, EyeOff, ZoomIn, ZoomOut } from "lucide-react";
import { useState } from "react";

export const Route = createFileRoute("/cases/$caseId/document/$docId")({
  head: () => ({ meta: [{ title: "Document Viewer · DocVerify" }] }),
  component: ViewerPage,
});

function ViewerPage() {
  const { caseId, docId } = useParams({ from: "/cases/$caseId/document/$docId" });
  const c = getCase(caseId);
  if (!c) return <AppShell><div>Case not found.</div></AppShell>;
  const idx = c.docs.findIndex((d) => d.id === docId);
  const doc = c.docs[idx];
  if (!doc) return <AppShell><div>Document not found.</div></AppShell>;
  const prev = c.docs[idx - 1];
  const next = c.docs[idx + 1];
  const [showHighlights, setShowHighlights] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [activeRegion, setActiveRegion] = useState<string | null>(null);
  const risk = riskLabel(doc.subScore);

  const docPages = (doc as any).pages || [];
  const [pageIdx, setPageIdx] = useState(0);

  return (
    <AppShell>
      <CaseBar
        applicant={c.applicant}
        caseId={c.id}
        amount={c.loanAmount}
        extra={
          <Link
            to="/cases/$caseId/report"
            params={{ caseId }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-xs"
          >
            <ChevronLeft className="size-3.5" /> Back to report
          </Link>
        }
      />

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border p-3">
            <div className="flex items-center gap-3">
              <div className="text-sm font-semibold">{doc.name}</div>
              <RiskPill level={risk} score={doc.subScore} />
            </div>
            <div className="flex items-center gap-1.5">
              {docPages.length > 1 && (
                <div className="flex items-center gap-1 border-r border-border pr-2 mr-2">
                  <button
                    disabled={pageIdx === 0}
                    onClick={() => setPageIdx(p => p - 1)}
                    className="rounded border border-border px-1.5 py-0.5 text-xs disabled:opacity-50 cursor-pointer hover:bg-secondary"
                  >
                    &lt;
                  </button>
                  <span className="text-xs text-muted-foreground px-1">
                    {pageIdx + 1} / {docPages.length}
                  </span>
                  <button
                    disabled={pageIdx === docPages.length - 1}
                    onClick={() => setPageIdx(p => p + 1)}
                    className="rounded border border-border px-1.5 py-0.5 text-xs disabled:opacity-50 cursor-pointer hover:bg-secondary"
                  >
                    &gt;
                  </button>
                </div>
              )}
              <IconBtn onClick={() => setShowHighlights((v) => !v)}>
                {showHighlights ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </IconBtn>
              <IconBtn onClick={() => setZoom((z) => Math.max(0.5, z - 0.1))}><ZoomOut className="size-4" /></IconBtn>
              <IconBtn onClick={() => setZoom((z) => Math.min(2, z + 0.1))}><ZoomIn className="size-4" /></IconBtn>
              <div className="px-2 text-xs text-muted-foreground">{Math.round(zoom * 100)}%</div>
              {prev && (
                <Link
                  to="/cases/$caseId/document/$docId" params={{ caseId, docId: prev.id }}
                  className="rounded-lg border border-border px-2 py-1 text-xs"
                >Prev</Link>
              )}
              {next && (
                <Link
                  to="/cases/$caseId/document/$docId" params={{ caseId, docId: next.id }}
                  className="rounded-lg border border-border px-2 py-1 text-xs"
                >Next</Link>
              )}
            </div>
          </div>
          <div className="bg-secondary p-6 overflow-auto flex justify-center items-center">
            <div
              className="bg-white shadow-md transition-all"
              style={{ width: 520 * zoom, height: 720 * zoom, position: "relative" }}
            >
              {docPages.length > 0 ? (
                <img
                  src={`data:image/png;base64,${docPages[pageIdx]}`}
                  alt={`Page ${pageIdx + 1}`}
                  style={{ width: "100%", height: "100%", objectFit: "contain" }}
                  className="select-none pointer-events-none"
                />
              ) : (
                <div className="absolute inset-6 space-y-3 text-[10px] text-gray-700">
                  <div className="text-center font-semibold">{doc.name.replace(/\.[a-z]+$/i, "")}</div>
                  <div className="h-px bg-gray-300" />
                  {Array.from({ length: 12 }).map((_, i) => (
                    <div key={i} className="h-2 bg-gray-100 rounded" style={{ width: `${60 + ((i * 13) % 35)}%` }} />
                  ))}
                  <div className="h-16" />
                  {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="h-2 bg-gray-100 rounded" style={{ width: `${50 + ((i * 11) % 40)}%` }} />
                  ))}
                </div>
              )}
              {showHighlights && doc.anomalyRegions.filter(r => docPages.length === 0 || r.page === pageIdx + 1).map((r) => (
                <button
                  key={r.id}
                  onClick={() => setActiveRegion(r.id)}
                  className="absolute border-2 border-[var(--risk-high)] bg-[var(--risk-high)]/15 hover:bg-[var(--risk-high)]/25 cursor-pointer"
                  style={{
                    left: `${r.box.x}%`, top: `${r.box.y}%`,
                    width: `${r.box.w}%`, height: `${r.box.h}%`,
                    outline: activeRegion === r.id ? "3px solid var(--risk-critical)" : undefined,
                  }}
                  title={r.label}
                />
              ))}
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="p-4">
            <h3 className="mb-3 text-sm font-semibold">Anomalies in this document</h3>
            {doc.anomalyRegions.length === 0 ? (
              <div className="text-xs text-muted-foreground">No anomalies detected.</div>
            ) : (
              <ul className="space-y-2">
                {doc.anomalyRegions.map((r) => (
                  <li key={r.id}>
                    <button
                      onClick={() => setActiveRegion(r.id)}
                      className={`w-full rounded-lg border px-3 py-2 text-left text-xs ${
                        activeRegion === r.id ? "border-primary bg-primary-soft" : "border-border bg-background"
                      }`}
                    >
                      <div className="font-medium">{r.label}</div>
                      <div className="mt-0.5 text-muted-foreground">Page {r.page}</div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="p-4 text-xs">
            <h3 className="mb-3 text-sm font-semibold">Metadata</h3>
            <dl className="space-y-1.5 text-muted-foreground">
              <Row label="File">{doc.name}</Row>
              <Row label="Created">{doc.metadata.created}</Row>
              <Row label="Modified">{doc.metadata.modified}</Row>
              <Row label="Software">{doc.metadata.software}</Row>
              <Row label="PDF version">{doc.metadata.pdfVersion}</Row>
              <Row label="Size">{doc.size}</Row>
            </dl>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

function IconBtn({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button onClick={onClick} className="grid size-8 place-items-center rounded-lg border border-border bg-surface hover:bg-secondary">
      {children}
    </button>
  );
}
function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <dt>{label}</dt>
      <dd className="text-foreground text-right">{children}</dd>
    </div>
  );
}