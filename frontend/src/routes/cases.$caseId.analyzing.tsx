import { createFileRoute, Link, useNavigate, useParams } from "@tanstack/react-router";
import { AppShell, Card } from "@/components/app-shell";
import { CaseBar } from "./cases.$caseId.upload";
import { getCase, saveCase, applyCaseResult } from "@/lib/mock-data";
import { analyzeCase, getCaseProgress, ApiError, type CaseProgress } from "@/lib/api";
import { Check, Loader2, Circle, AlertTriangle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export const Route = createFileRoute("/cases/$caseId/analyzing")({
  head: () => ({ meta: [{ title: "Analyzing · DocVerify" }] }),
  component: AnalyzingPage,
});

// Real backend phases (see backend/app.py::ANALYZE_PHASES), labeled for the
// UI. "running_pipeline" covers OCR/forensics/cross-doc/registry/scoring in
// one opaque model-service call — the backend can't report finer-grained
// progress inside that call without its own instrumentation, so this step
// legitimately takes the longest.
const PHASE_STEPS: { key: CaseProgress["phase"]; label: string }[] = [
  { key: "checking_ledger", label: "Checking On-Chain Ledger Cache" },
  { key: "running_pipeline", label: "Running Detection Pipeline (OCR, Forensics, Cross-Checks, Registry)" },
  { key: "recording_audit", label: "Recording Audit Trail (L7 Hash-Chain)" },
  { key: "persisting_case", label: "Persisting Case Result" },
  { key: "anchoring_ledger", label: "Anchoring Result to Ledger" },
];

const PROGRESS_POLL_MS = 800;
const MAX_POLL_FAILURES = 5;

function AnalyzingPage() {
  const { caseId } = useParams({ from: "/cases/$caseId/analyzing" });
  const c = getCase(caseId);
  const navigate = useNavigate();
  const [phase, setPhase] = useState<CaseProgress["phase"]>("idle");
  const [pollingLost, setPollingLost] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState(false);
  const started = useRef(false);

  // Kick off the real analysis exactly once.
  useEffect(() => {
    if (started.current) return;
    started.current = true;

    if (c && c.status !== "Processing") {
      c.status = "Processing";
      saveCase(c);
    }

    analyzeCase(caseId)
      .then((result) => {
        applyCaseResult(caseId, result);
        setDone(true);
        setPhase("done");
        setTimeout(() => navigate({ to: "/cases/$caseId/report", params: { caseId } }), 600);
      })
      .catch((err) => setError(err));
  }, [caseId, c, navigate]);

  // Poll the backend for its real current phase. A skipped phase (e.g. a
  // ledger cache hit skips "running_pipeline"/"anchoring_ledger") is fine —
  // stepIdx below just jumps ahead, which honestly reflects that the backend
  // genuinely skipped that work. If polling itself breaks (network hiccup,
  // dropped connection), fall back to a plain spinner rather than getting
  // stuck on a stale step — the analyzeCase() promise above is still the
  // source of truth for navigating to the report page.
  useEffect(() => {
    if (error || done) return;
    let cancelled = false;
    let failures = 0;
    const poll = async () => {
      try {
        const p = await getCaseProgress(caseId);
        if (cancelled) return;
        failures = 0;
        setPollingLost(false);
        setPhase(p.phase);
      } catch {
        failures += 1;
        if (failures >= MAX_POLL_FAILURES) setPollingLost(true);
      }
    };
    poll();
    const t = setInterval(poll, PROGRESS_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [caseId, error, done]);

  const stepIdx = pollingLost
    ? -1
    : phase === "done"
    ? PHASE_STEPS.length
    : Math.max(0, PHASE_STEPS.findIndex((s) => s.key === phase));

  if (error) {
    const detail =
      error instanceof ApiError
        ? typeof error.detail === "string"
          ? error.detail
          : JSON.stringify(error.detail)
        : error instanceof Error
        ? error.message
        : "Analysis failed.";
    return (
      <AppShell>
        <CaseBar applicant={c?.applicant ?? "Applicant"} caseId={caseId} amount={c?.loanAmount ?? 0} />
        <Card className="p-8 max-w-3xl mx-auto text-center">
          <div className="mx-auto grid size-16 place-items-center rounded-full bg-destructive/10">
            <AlertTriangle className="size-7 text-destructive" />
          </div>
          <h2 className="mt-5 text-xl font-semibold">Analysis could not complete</h2>
          <p className="mt-2 text-sm text-muted-foreground break-words">{detail}</p>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              to="/cases/$caseId/upload"
              params={{ caseId }}
              className="rounded-lg border border-border bg-surface px-4 py-2.5 text-sm"
            >
              Back to upload
            </Link>
            <Link to="/dashboard" className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground">
              Return to dashboard
            </Link>
          </div>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <CaseBar applicant={c?.applicant ?? "Applicant"} caseId={caseId} amount={c?.loanAmount ?? 0} />
      <Card className="p-8 max-w-3xl mx-auto">
        <div className="text-center">
          <div className="mx-auto grid size-16 place-items-center rounded-full bg-primary-soft">
            <Loader2 className="size-7 animate-spin text-primary" />
          </div>
          <h2 className="mt-5 text-xl font-semibold">Analyzing {c?.docs.length ?? ""} documents</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Running the real detection pipeline across the security and model services. This can take a moment.
          </p>
        </div>

        {pollingLost ? (
          <div className="mt-8 rounded-lg border border-border bg-background px-4 py-6 text-center text-sm text-muted-foreground">
            Lost the live progress feed — still waiting on the backend to finish. This page will
            move on automatically once the result is ready.
          </div>
        ) : (
          <div className="mt-8 space-y-2">
            {PHASE_STEPS.map((s, i) => {
              const state = i < stepIdx ? "done" : i === stepIdx ? "active" : "pending";
              return (
                <div
                  key={s.key}
                  className={`flex items-center gap-3 rounded-lg border px-4 py-3 ${
                    state === "active" ? "border-primary bg-primary-soft" : "border-border bg-background"
                  }`}
                >
                  {state === "done" && (
                    <div className="grid size-7 place-items-center rounded-full bg-[var(--success)] text-white">
                      <Check className="size-4" />
                    </div>
                  )}
                  {state === "active" && (
                    <div className="grid size-7 place-items-center rounded-full bg-primary text-primary-foreground">
                      <Loader2 className="size-4 animate-spin" />
                    </div>
                  )}
                  {state === "pending" && (
                    <div className="grid size-7 place-items-center rounded-full bg-secondary text-muted-foreground">
                      <Circle className="size-3" />
                    </div>
                  )}
                  <div className="text-sm font-medium">{s.label}</div>
                  <div className="ml-auto text-xs text-muted-foreground capitalize">{state}</div>
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-8 text-center">
          <Link to="/dashboard" className="text-sm text-primary hover:underline">
            Return to dashboard — we'll notify you
          </Link>
        </div>
      </Card>
    </AppShell>
  );
}
