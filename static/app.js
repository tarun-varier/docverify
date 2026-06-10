"use strict";

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const fileList = document.getElementById("file-list");
const analyzeBtn = document.getElementById("analyze-btn");
const progress = document.getElementById("progress");
const errorBox = document.getElementById("error");
const results = document.getElementById("results");

let bundle = [];

function esc(s) {
  const div = document.createElement("div");
  div.textContent = String(s ?? "");
  return div.innerHTML;
}

function renderFileList() {
  fileList.innerHTML = bundle
    .map((f, i) =>
      `<li><span>📄 ${esc(f.name)} <small>(${(f.size / 1024).toFixed(0)} KB)</small></span>
       <button class="rm" data-i="${i}" title="Remove">✕</button></li>`)
    .join("");
  analyzeBtn.disabled = bundle.length === 0;
}

function addFiles(files) {
  for (const f of files) {
    if (!bundle.some((b) => b.name === f.name && b.size === f.size)) bundle.push(f);
  }
  renderFileList();
}

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => { if (e.key === "Enter") fileInput.click(); });
fileInput.addEventListener("change", () => { addFiles(fileInput.files); fileInput.value = ""; });
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  addFiles(e.dataTransfer.files);
});
fileList.addEventListener("click", (e) => {
  if (e.target.classList.contains("rm")) {
    bundle.splice(Number(e.target.dataset.i), 1);
    renderFileList();
  }
});

analyzeBtn.addEventListener("click", async () => {
  errorBox.hidden = true;
  progress.hidden = false;
  analyzeBtn.disabled = true;
  const form = new FormData();
  bundle.forEach((f) => form.append("files", f));
  try {
    const res = await fetch("/api/analyze", { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Server error (${res.status})`);
    }
    renderResults(await res.json());
  } catch (err) {
    errorBox.textContent = err.message;
    errorBox.hidden = false;
  } finally {
    progress.hidden = true;
    analyzeBtn.disabled = bundle.length === 0;
  }
});

function bandClass(band) { return band.toLowerCase(); }

function renderGauge(score, band) {
  const arc = document.getElementById("gauge-arc");
  const len = 251.3;
  arc.style.strokeDashoffset = String(len * (1 - score / 100));
  arc.style.stroke =
    { LOW: "#16a34a", MEDIUM: "#d97706", HIGH: "#ea580c", CRITICAL: "#dc2626" }[band];
  document.getElementById("gauge-score").textContent = score;
  const bandEl = document.getElementById("risk-band");
  bandEl.textContent = `${band} RISK`;
  bandEl.className = `band ${bandClass(band)}`;
}

function anomalyCard(a) {
  return `<div class="anomaly ${bandClass(a.severity)}">
    <div class="head">
      <span class="tag ${bandClass(a.severity)}">${esc(a.severity)}</span>
      <span class="tag layer">${esc(a.layer.replace("_", " "))}</span>
      <strong>${esc(a.title)}</strong>
    </div>
    <p>${esc(a.detail)}</p>
    ${a.documents.length ? `<div class="docs">Documents: ${a.documents.map(esc).join(", ")}</div>` : ""}
  </div>`;
}

function fieldRows(fields) {
  const labels = {
    applicant_name: "Name", pan: "PAN", cin: "CIN", survey_number: "Survey No.",
    monthly_income: "Monthly income", registration_date: "Registration date", address: "Address",
  };
  let rows = "";
  for (const [key, label] of Object.entries(labels)) {
    const v = fields[key];
    if (v) rows += `<dt>${label}</dt><dd>${esc(v)}</dd>`;
  }
  if (fields.salary_credits?.length) {
    rows += `<dt>Salary credits</dt><dd>₹${fields.salary_credits
      .map((c) => c.toLocaleString("en-IN")).join(", ₹")}</dd>`;
  }
  return rows;
}

function docCard(d) {
  const ela = d.ela_image
    ? `<img class="ela" src="data:image/png;base64,${d.ela_image}"
         alt="ELA heatmap — bright regions indicate possible edits">`
    : "";
  return `<div class="doc">
    <div class="head">
      <strong>📄 ${esc(d.filename)}</strong>
      <span class="type">${esc(d.doc_type.replace("_", " "))}</span>
    </div>
    <dl>
      ${fieldRows(d.fields)}
      <dt>Pages</dt><dd>${d.page_count}${d.ocr_used ? " (OCR)" : ""}</dd>
      <dt>SHA-256</dt><dd>${esc(d.sha256.slice(0, 24))}…</dd>
    </dl>
    ${d.anomalies.map(anomalyCard).join("")}
    ${ela}
  </div>`;
}

function renderResults(r) {
  results.hidden = false;
  renderGauge(r.fraud_score, r.risk_band);
  document.getElementById("recommended-action").textContent = r.recommended_action;
  document.getElementById("case-meta").textContent =
    `Case ${r.case_id} · ${r.documents.length} document(s) · analyzed in ${r.elapsed_seconds}s · ` +
    `audit entry ${r.audit_entry.entry_hash.slice(0, 16)}…`;
  document.getElementById("recommendations").innerHTML =
    r.recommendations.length
      ? r.recommendations.map((x) => `<li>${esc(x)}</li>`).join("")
      : "<li>No specific actions required.</li>";

  const allAnomalies = [
    ...r.documents.flatMap((d) => d.anomalies),
    ...r.cross_document_anomalies,
    ...r.registry_anomalies,
  ];
  document.getElementById("anomalies").innerHTML = allAnomalies.length
    ? allAnomalies.map(anomalyCard).join("")
    : `<p class="ok-note">✅ No anomalies detected across any layer.</p>`;

  document.getElementById("documents").innerHTML = r.documents.map(docCard).join("");
  results.scrollIntoView({ behavior: "smooth" });
}

(async function auditStatus() {
  const chip = document.getElementById("audit-status");
  try {
    const res = await fetch("/api/audit/verify");
    const { intact, entries } = await res.json();
    chip.textContent = intact ? `audit ledger intact · ${entries} entries` : "audit ledger BROKEN";
    chip.classList.add(intact ? "ok" : "bad");
  } catch {
    chip.textContent = "audit: unavailable";
  }
})();
