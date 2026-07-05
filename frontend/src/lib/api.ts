// Backend API base URL + typed helpers for the real analysis path:
//   POST /cases/:id/documents   → scan one file (Layer-0 gate) and buffer it
//   POST /cases/:id/analyze      → run the full pipeline, return a CaseResult

export const API_BASE_URL = (() => {
  const configured = import.meta.env.VITE_API_URL ?? import.meta.env.VITE_BACKEND_URL;
  if (configured) return String(configured).replace(/\/$/, "");
  if (typeof window !== "undefined" && window.location.hostname) {
    const host = window.location.hostname === "localhost" ? "127.0.0.1" : window.location.hostname;
    return `${window.location.protocol}//${host}:8000`;
  }
  return "http://127.0.0.1:8000";
})();

export interface DocumentAccepted {
  status: string;
  case_id: string;
  filename: string | null;
  sha256: string;
  page_count: number;
  pdf_anomaly_count: number;
  documents_buffered: number;
}

export class ApiError extends Error {
  detail: unknown;
  status: number;
  constructor(detail: unknown, status: number) {
    super(typeof detail === "string" ? detail : "Request failed");
    this.detail = detail;
    this.status = status;
  }
}

async function parseOrThrow(res: Response) {
  const payload = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload ? (payload as any).detail : payload;
    throw new ApiError(detail ?? "The security gateway or backend returned an error.", res.status);
  }
  return payload;
}

/** Upload + Layer-0 scan one document into a case. Throws ApiError on rejection. */
export async function uploadDocument(
  caseId: string,
  file: File,
  category: "land" | "legal" | "financial",
): Promise<DocumentAccepted> {
  const form = new FormData();
  form.append("file", file);
  form.append("category", category);
  const res = await fetch(`${API_BASE_URL}/cases/${encodeURIComponent(caseId)}/documents`, {
    method: "POST",
    body: form,
  });
  return parseOrThrow(res);
}

/** Run the full analysis over a case's buffered documents. Returns a CaseResult. */
export async function analyzeCase(caseId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/cases/${encodeURIComponent(caseId)}/analyze`, {
    method: "POST",
  });
  return parseOrThrow(res);
}
