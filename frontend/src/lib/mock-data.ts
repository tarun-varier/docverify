export type RiskLevel = "low" | "medium" | "high" | "critical";
export type CaseStatus = "Uploading" | "Processing" | "Ready for Review" | "Decision Recorded";
export type Decision = "Approved" | "Approved with Conditions" | "Escalated" | "Rejected" | "Resubmission Requested";

export interface Anomaly {
  id: string;
  title: string;
  category: "Tamper Detection" | "Cross-Document Conflict" | "Metadata Anomaly" | "Registry Mismatch";
  severity: RiskLevel;
  detail: string;
  documentIds?: string[];
}

export interface CaseDoc {
  id: string;
  name: string;
  category: "land" | "legal" | "financial";
  size: string;
  subScore: number;
  summary: string;
  metadata: { created: string; modified: string; software: string; pdfVersion: string };
  anomalyRegions: { id: string; page: number; label: string; box: { x: number; y: number; w: number; h: number } }[];
}

export interface Case {
  id: string;
  applicant: string;
  pan: string;
  loanType: string;
  loanAmount: number;
  branch: string;
  officer: string;
  submittedAt: string;
  status: CaseStatus;
  score: number;
  risk: RiskLevel;
  docs: CaseDoc[];
  anomalies: Anomaly[];
  conflicts: { id: string; description: string; documentIds: string[] }[];
  external: { check: string; status: "passed" | "failed" | "inconclusive"; detail: string }[];
  decision?: { type: Decision; notes: string; by: string; at: string };
  hash: string;
  auditId: string;
}

export const riskLabel = (s: number): RiskLevel =>
  s >= 80 ? "critical" : s >= 60 ? "high" : s >= 35 ? "medium" : "low";

const baseDocs = (caseId: string): CaseDoc[] => [
  {
    id: `${caseId}-d1`,
    name: "Property_Deed_2019.pdf",
    category: "land",
    size: "1.8 MB",
    subScore: 78,
    summary: "Registration date inconsistencies detected. Recent ownership transfer flagged.",
    metadata: { created: "2024-11-08", modified: "2024-11-09", software: "Adobe Acrobat Pro DC", pdfVersion: "1.7" },
    anomalyRegions: [
      { id: "r1", page: 1, label: "Seal appears copy-pasted", box: { x: 60, y: 18, w: 22, h: 14 } },
      { id: "r2", page: 2, label: "Font inconsistency on date", box: { x: 20, y: 60, w: 30, h: 6 } },
    ],
  },
  {
    id: `${caseId}-d2`,
    name: "PAN_Card.jpg",
    category: "legal",
    size: "420 KB",
    subScore: 22,
    summary: "PAN structure valid. No tamper indicators.",
    metadata: { created: "2024-11-06", modified: "2024-11-06", software: "Camera", pdfVersion: "—" },
    anomalyRegions: [],
  },
  {
    id: `${caseId}-d3`,
    name: "Application_Form_Signed.pdf",
    category: "legal",
    size: "612 KB",
    subScore: 64,
    summary: "Signature differs from ID proof. Recommend video KYC.",
    metadata: { created: "2024-11-07", modified: "2024-11-07", software: "Adobe Acrobat", pdfVersion: "1.6" },
    anomalyRegions: [
      { id: "r3", page: 3, label: "Signature mismatch with PAN", box: { x: 55, y: 70, w: 30, h: 12 } },
    ],
  },
  {
    id: `${caseId}-d4`,
    name: "Salary_Slip_Oct.pdf",
    category: "financial",
    size: "240 KB",
    subScore: 71,
    summary: "Declared income contradicts bank statement averages.",
    metadata: { created: "2024-11-05", modified: "2024-11-05", software: "Microsoft Word", pdfVersion: "1.5" },
    anomalyRegions: [
      { id: "r4", page: 1, label: "Net pay figure altered", box: { x: 55, y: 45, w: 25, h: 8 } },
    ],
  },
  {
    id: `${caseId}-d5`,
    name: "Bank_Statement_6mo.pdf",
    category: "financial",
    size: "2.1 MB",
    subScore: 18,
    summary: "Statement consistent. Average credit ₹40,200/mo.",
    metadata: { created: "2024-11-05", modified: "2024-11-05", software: "Banking Portal", pdfVersion: "1.7" },
    anomalyRegions: [],
  },
];

const mkCase = (
  id: string,
  applicant: string,
  loanType: string,
  loanAmount: number,
  branch: string,
  status: CaseStatus,
  score: number,
  submittedAt: string,
  decision?: Case["decision"],
): Case => ({
  id,
  applicant,
  pan: "ABCDE1234F",
  loanType,
  loanAmount,
  branch,
  officer: "Anita Verma",
  submittedAt,
  status,
  score,
  risk: riskLabel(score),
  docs: baseDocs(id),
  anomalies: [
    { id: "a1", title: "Signature mismatch between ID proof and application form", category: "Cross-Document Conflict", severity: "high", detail: "Stroke pressure and slant differ materially. Recommend video KYC before approval.", documentIds: [`${id}-d2`, `${id}-d3`] },
    { id: "a2", title: "Land record ownership changed 15 days before application", category: "Registry Mismatch", severity: "critical", detail: "State land registry shows transfer dated 24-Oct-2024. High flip risk.", documentIds: [`${id}-d1`] },
    { id: "a3", title: "Document metadata shows creation date 2 days before submission but claims registration year 2019", category: "Metadata Anomaly", severity: "high", detail: "Possible backdating. PDF created 08-Nov-2024 via Adobe Acrobat Pro DC.", documentIds: [`${id}-d1`] },
    { id: "a4", title: "Salary slip net pay region shows pixel-level tampering", category: "Tamper Detection", severity: "medium", detail: "Error Level Analysis indicates an altered numeric region in the net pay field.", documentIds: [`${id}-d4`] },
  ],
  conflicts: [
    { id: "c1", description: "Salary slip claims ₹80,000 monthly income; bank statement shows ₹40,200 average credit.", documentIds: [`${id}-d4`, `${id}-d5`] },
    { id: "c2", description: "Property deed registration year (2019) contradicts metadata creation date (2024).", documentIds: [`${id}-d1`] },
  ],
  external: [
    { check: "PAN structure validation", status: "passed", detail: "Format valid. Active." },
    { check: "CIN status check", status: "inconclusive", detail: "Not applicable for individual borrower." },
    { check: "Land registry correlation (CERSAI mock)", status: "failed", detail: "Owner name on registry differs from applicant." },
  ],
  decision,
  hash: "0x7a8f…b2d3",
  auditId: `AL-${id}`,
});

const mockCasesInitial: Case[] = [
  mkCase("3G327H", "Jeff Henry", "Home Loan", 4500000, "Howeville", "Ready for Review", 78, "2024-11-10"),
  mkCase("G327H", "Marc Shaw", "Business Loan", 1200000, "Howeville", "Ready for Review", 52, "2024-11-10"),
  mkCase("453227H", "Evelyn Lopez", "Personal Loan", 250000, "East Nash", "Processing", 0, "2024-11-10"),
  mkCase("453227X", "Hattie Cobb", "Home Loan", 6800000, "Gutkowski", "Decision Recorded", 22, "2024-11-09", {
    type: "Approved", notes: "Clean review.", by: "Anita Verma", at: "2024-11-09 14:22",
  }),
  mkCase("394NHS", "Bobby Page", "Auto Loan", 800000, "South Lillybury", "Decision Recorded", 88, "2024-11-08", {
    type: "Rejected", notes: "Critical tamper indicators across two documents.", by: "Anita Verma", at: "2024-11-08 11:05",
  }),
  mkCase("453228D", "Daniel Harper", "Home Loan", 3200000, "East Nash", "Ready for Review", 41, "2024-11-08"),
];

export const mockCases: Case[] = [];

if (typeof window !== "undefined") {
  try {
    const data = localStorage.getItem("docverify_cases");
    if (data) {
      mockCases.push(...JSON.parse(data));
    } else {
      mockCases.push(...mockCasesInitial);
      localStorage.setItem("docverify_cases", JSON.stringify(mockCasesInitial));
    }
  } catch (e) {
    mockCases.push(...mockCasesInitial);
  }
} else {
  mockCases.push(...mockCasesInitial);
}

export const getCase = (id: string) => mockCases.find((c) => c.id === id);

export const saveCase = (c: Case) => {
  const idx = mockCases.findIndex((x) => x.id === c.id);
  if (idx > -1) {
    mockCases[idx] = c;
  } else {
    mockCases.push(c);
  }
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem("docverify_cases", JSON.stringify(mockCases));
    } catch (e) {
      console.error(e);
    }
  }
};

// ---------------------------------------------------------------------------
// Real-analysis adapter
//
// Maps a backend CaseResult (model /analyze output) onto the UI's Case shape so
// the existing report / document / decision screens render real data with no
// rewrite. The pipeline scores at the case level, so per-document subScores are
// reconstructed from each document's own anomalies using the same severity
// weights the backend uses.
// ---------------------------------------------------------------------------

export interface RealAnomaly {
  code: string;
  layer: string;
  severity: string;
  title: string;
  detail: string;
  documents?: string[];
  evidence?: Record<string, unknown>;
}

export interface RealDocReport {
  filename: string;
  sha256: string;
  doc_type: string;
  page_count: number;
  text_chars: number;
  ocr_used: boolean;
  fields: Record<string, unknown>;
  metadata: Record<string, unknown>;
  anomalies: RealAnomaly[];
  ela_image?: string | null;
  suspicious_regions?: unknown[];
}

export interface CaseResult {
  case_id: string;
  analyzed_at: string;
  elapsed_seconds: number;
  fraud_score: number;
  risk_band: string;
  recommended_action: string;
  recommendations: string[];
  documents: RealDocReport[];
  cross_document_anomalies: RealAnomaly[];
  registry_anomalies: RealAnomaly[];
  llm_summary?: Record<string, unknown>;
  audit_entry?: { entry_hash?: string } & Record<string, unknown>;
}

const SEV_WEIGHT: Record<string, number> = { info: 0, low: 6, medium: 14, high: 26, critical: 40 };

const toRisk = (s: string): RiskLevel =>
  s === "critical" ? "critical" : s === "high" ? "high" : s === "medium" ? "medium" : "low";

const catFromDocType = (t: string): "land" | "legal" | "financial" =>
  t === "salary_slip" || t === "bank_statement" ? "financial" : t === "land_record" ? "land" : "legal";

const uiCategory = (a: RealAnomaly): Anomaly["category"] => {
  if (a.layer === "cross_document") return "Cross-Document Conflict";
  if (a.layer === "registry") return "Registry Mismatch";
  const code = (a.code || "").toLowerCase();
  if (/meta|backdat|software|eof|modif|producer|creat/.test(code)) return "Metadata Anomaly";
  return "Tamper Detection";
};

const pickMeta = (md: Record<string, unknown> | undefined, keys: string[]): string => {
  if (!md) return "—";
  for (const k of keys) {
    for (const cand of [k, "/" + k, k.toLowerCase()]) {
      const v = md[cand];
      if (v != null && String(v).trim()) return String(v);
    }
  }
  return "—";
};

export function applyCaseResult(caseId: string, result: CaseResult): Case | undefined {
  const c = getCase(caseId);
  if (!c) return undefined;

  const docs: CaseDoc[] = result.documents.map((d, i) => {
    const subScore = Math.min(
      100,
      d.anomalies.reduce((s, a) => s + (SEV_WEIGHT[a.severity] ?? 0), 0),
    );
    const top = [...d.anomalies].sort(
      (a, b) => (SEV_WEIGHT[b.severity] ?? 0) - (SEV_WEIGHT[a.severity] ?? 0),
    )[0];
    return {
      id: `${caseId}-d${i + 1}`,
      name: d.filename,
      category: catFromDocType(d.doc_type),
      size: `${d.page_count} pp`,
      subScore,
      summary:
        top?.detail ||
        (d.doc_type !== "unknown"
          ? `Classified as ${d.doc_type.replace(/_/g, " ")}. No tamper indicators.`
          : "No tamper indicators detected."),
      metadata: {
        created: pickMeta(d.metadata, ["CreationDate", "creation_date", "created"]),
        modified: pickMeta(d.metadata, ["ModDate", "modified", "mod_date"]),
        software: pickMeta(d.metadata, ["Producer", "Creator", "software", "producer", "creator"]),
        pdfVersion: pickMeta(d.metadata, ["PDFVersion", "pdf_version", "version"]),
      },
      anomalyRegions: [],
    };
  });

  const idOfFile = (fn: string) => docs.find((d) => d.name === fn)?.id;

  const allAnoms: RealAnomaly[] = [
    ...result.documents.flatMap((d) => d.anomalies),
    ...result.cross_document_anomalies,
    ...result.registry_anomalies,
  ];

  const anomalies: Anomaly[] = allAnoms.map((a, i) => ({
    id: `an-${caseId}-${i}`,
    title: a.title || a.code,
    category: uiCategory(a),
    severity: toRisk(a.severity),
    detail: a.detail,
    documentIds: (a.documents || []).map(idOfFile).filter(Boolean) as string[],
  }));

  const conflicts = result.cross_document_anomalies.map((a, i) => ({
    id: `cf-${caseId}-${i}`,
    description: a.detail || a.title,
    documentIds: (a.documents || []).map(idOfFile).filter(Boolean) as string[],
  }));

  const totalPages = result.documents.reduce((n, d) => n + (d.page_count || 0), 0);
  const external: Case["external"] = [
    { check: "Layer 0 Security Scan", status: "passed", detail: "Static analysis clean; no JavaScript/OpenAction/Launch payloads." },
    { check: "CDR Sanitization", status: "passed", detail: `Rendered ${totalPages} page(s) into flat, safe pixels.` },
  ];
  for (const a of result.registry_anomalies) {
    external.push({ check: a.title || a.code, status: "failed", detail: a.detail });
  }
  if (result.registry_anomalies.length === 0) {
    external.push({ check: "Registry Correlation", status: "passed", detail: "No registry mismatches detected." });
  }

  const score = Math.round(result.fraud_score);
  let risk = (result.risk_band ? result.risk_band.toLowerCase() : riskLabel(score)) as RiskLevel;
  if (!["low", "medium", "high", "critical"].includes(risk)) risk = riskLabel(score);

  c.docs = docs;
  c.anomalies = anomalies;
  c.conflicts = conflicts;
  c.external = external;
  c.score = score;
  c.risk = risk;
  c.status = "Ready for Review";
  c.hash = result.audit_entry?.entry_hash
    ? `0x${String(result.audit_entry.entry_hash).slice(0, 12)}…`
    : c.hash;
  c.auditId = result.case_id;
  saveCase(c);
  return c;
}

export const mockUsers = [
  { id: "U001", name: "Anita Verma", employeeId: "EMP-1042", email: "anita.verma@bank.in", role: "Underwriter", branch: "Howeville", status: "Active", lastLogin: "2024-11-10 09:14" },
  { id: "U002", name: "Rohit Mehta", employeeId: "EMP-1108", email: "rohit.mehta@bank.in", role: "Senior Underwriter", branch: "East Nash", status: "Active", lastLogin: "2024-11-10 08:55" },
  { id: "U003", name: "Sara Iyer", employeeId: "EMP-1199", email: "sara.iyer@bank.in", role: "Underwriter", branch: "Gutkowski", status: "Inactive", lastLogin: "2024-10-28 17:32" },
  { id: "U004", name: "Vikram Singh", employeeId: "EMP-1221", email: "vikram.singh@bank.in", role: "Admin", branch: "HQ", status: "Active", lastLogin: "2024-11-10 10:02" },
];

export const integrations = [
  { name: "CERSAI", status: "Connected (Test)", updated: "2024-11-01" },
  { name: "ROC (Registrar of Companies)", status: "Connected (Test)", updated: "2024-10-28" },
  { name: "State Land Records API", status: "Pending", updated: "2024-10-15" },
  { name: "PAN/NSDL Validation", status: "Connected (Test)", updated: "2024-11-05" },
];