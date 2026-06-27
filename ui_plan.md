# DocVerify MVP — UI Development Plan

---

## Overview

The primary user is a **bank underwriter or loan processing officer**. The secondary user is a **bank admin** who manages the system. The journey flows from login → case creation → document upload → automated analysis → results review → underwriting decision → audit. Every screen below maps to a step in that journey.

---

## Screen 1: Login & Authentication

**Purpose:** Secure entry point for bank staff. Ensures only authorized personnel access sensitive loan documents and fraud results.

**What it shows:**
- Bank logo and DocVerify branding
- Email/employee ID input field
- Password input field
- "Forgot Password" link
- Login button
- A brief tagline reinforcing the product's purpose (e.g., "AI-powered document verification for smarter underwriting")
- No registration option — accounts are provisioned by the admin

**What the user can do:**
- Enter credentials and log in
- Request a password reset via email
- Nothing else — no public-facing content or self-signup

---

## Screen 2: Main Dashboard (Home)

**Purpose:** Central command center. Gives the officer an at-a-glance view of all active and historical loan cases, workload, and system-level fraud trends.

**What it shows:**
- Top navigation bar with the product logo, the logged-in officer's name/role, and a notification bell
- Summary stats row: total cases today, cases pending review, cases flagged as high risk, cases cleared
- A filterable, sortable case table with columns for: Case ID, Applicant Name, Loan Type, Date Submitted, Documents Uploaded (count), Analysis Status, Fraud Risk Score, and Action button
- Analysis status represented as a text label: Uploading, Processing, Ready for Review, Decision Recorded
- A color-coded risk indicator beside each score: green (low), amber (medium), red (high)
- Pagination or infinite scroll for the case list

**What the user can do:**
- Click "New Case" to begin a fresh loan verification workflow
- Search cases by applicant name, Case ID, or date range
- Filter by status (pending, processed, decided) or risk level
- Sort the table by any column
- Click on any case row to open that case's detail screen
- Log out via the navigation bar

---

## Screen 3: New Case Creation

**Purpose:** Captures the basic loan application context before any documents are uploaded. Establishes the case record and links all subsequent documents to a single applicant and loan request.

**What it shows:**
- A simple form with clearly labeled sections
- Applicant Information section: Full name, PAN number, Aadhaar number (masked), date of birth, contact number, address
- Loan Details section: Loan type (home loan, business loan, personal loan, etc.), loan amount requested, branch name or branch code, assigned officer name (pre-filled with the logged-in user)
- A "Proceed to Document Upload" button
- A "Save as Draft" option

**What the user can do:**
- Fill in applicant and loan details
- Save as draft to return later
- Proceed to the document upload screen once all required fields are complete
- Navigate back to the dashboard without saving

---

## Screen 4: Document Upload

**Purpose:** Collects all documents needed for the verification run. Organizes them into the three categories the system understands — land records, legal documents, and financial statements — so the cross-document analysis engine knows what it is comparing.

**What it shows:**
- Case summary bar at the top showing the applicant name, Case ID, and loan amount (carried forward from Screen 3)
- Three clearly labeled upload sections, each as a distinct panel:
  - **Land Records & Property:** Land deeds, survey documents, property registration papers
  - **Legal & Identity Documents:** ID proofs, application form, NOC, legal agreements
  - **Financial Statements:** Salary slips, bank statements, ITR, Form 16
- Each panel shows accepted file formats (PDF, JPG, PNG) and maximum file size
- A file list within each panel as documents are added, showing file name, file size, and a remove button
- Upload progress bar per file
- A prominent "Run Analysis" button that activates only when at least one document is present in any panel
- A note clarifying that uploading more documents enables cross-document checks

**What the user can do:**
- Drag and drop files or click to browse and select files for each category
- Upload multiple files per category
- Remove any incorrectly added file before running analysis
- Initiate the analysis run
- Navigate back to the case creation form to edit applicant details

---

## Screen 5: Analysis in Progress

**Purpose:** Communicates that the system is actively working. Manages the officer's expectation during the 90-second processing window and prevents repeated re-uploads or confusion about system state.

**What it shows:**
- The case summary bar (applicant name, Case ID) at the top
- A central processing indicator — a progress animation or a step-by-step status tracker
- Status steps shown in sequence as they complete:
  1. Document Ingestion & OCR
  2. Tamper & Metadata Forensics
  3. Visual Forgery Analysis
  4. Cross-Document Consistency Check
  5. External Registry Correlation
  6. Risk Score Computation
- Each step shows as pending, active, or complete
- An estimated time remaining (e.g., "Results ready in ~60 seconds")
- The number of documents being analyzed
- A note that the officer can leave this screen and return — the system will continue processing and notify them when done

**What the user can do:**
- Wait on the screen to see results load automatically when complete
- Navigate away to the dashboard; the case will update to "Ready for Review" status
- Cannot cancel mid-analysis once triggered

---

## Screen 6: Case Analysis Report (Core Screen)

**Purpose:** This is the primary decision-support screen — the bank officer dashboard described in the product spec. It presents the full fraud risk assessment in a structured, actionable format so the underwriter can make an informed call without digging through raw documents.

**What it shows:**

**Header zone:**
- Case summary bar: applicant name, loan type, loan amount, Case ID, date analyzed
- Overall Fraud Confidence Score displayed prominently as a number (0–100) with a risk label (Low / Medium / High / Critical) and a color indicator

**Intelligent Insights panel:**
- A prioritized list of specific anomaly alerts generated by the system, each written in plain language. Examples as described in the spec:
  - "Signature mismatch between ID proof and application form. Recommend video KYC."
  - "Land record ownership changed 15 days before application. High flip risk."
  - "Document metadata shows creation date 2 days before submission but claims registration year 2019. Possible backdating."
- Each insight tagged by category: Tamper Detection, Cross-Document Conflict, Metadata Anomaly, Registry Mismatch
- Each insight tagged by severity: Critical, High, Medium, Low
- Insights sorted by severity by default

**Per-Document Results panel:**
- A list of each uploaded document with its individual risk sub-score
- A brief summary of what was found in that document
- A "View Document" button that opens the Document Viewer (Screen 7)

**Cross-Document Conflict panel (if applicable):**
- Specific pairs or groups of documents that contradict each other
- Clear description of the conflict (e.g., "Salary slip claims ₹80,000 income; bank statement shows ₹40,000 average credit")
- The documents involved, with links to view each

**External Correlation panel:**
- Results of PAN structure validation, CIN status check, and land registry correlation
- Each check shown as passed, failed, or inconclusive

**What the user can do:**
- Read and review all insights and anomalies
- Click on any insight to expand it for more detail
- Click "View Document" on any document entry to open the annotated document viewer
- Click "Record Decision" to proceed to the underwriting action screen (Screen 8)
- Download the full report as a PDF for offline sharing or filing
- Add internal notes or comments to the case

---

## Screen 7: Document Viewer (Annotated)

**Purpose:** Lets the officer examine a specific document in detail, with suspicious regions visually highlighted and annotated by the system. Provides the evidence layer that backs up the insights shown on the Case Report screen.

**What it shows:**
- The document rendered page by page (PDF viewer style)
- Highlighted or outlined regions on the document where anomalies were detected — for example, a bounding box around a suspected copy-pasted seal, an underlined font inconsistency, or a shaded region flagged by Error Level Analysis
- A sidebar panel listing all anomalies detected in this specific document, with each anomaly linked to the corresponding highlighted region on the document
- Clicking an anomaly in the sidebar scrolls the document to that region and vice versa
- Document metadata panel: file name, creation date, last modified date, software used (e.g., "Edited in Adobe Acrobat"), PDF version
- The document's individual fraud sub-score at the top

**What the user can do:**
- Scroll through document pages
- Click anomaly entries in the sidebar to jump to the flagged region
- Zoom in or out on the document
- Toggle highlights on or off to see the clean document underneath
- Navigate between documents in this case using prev/next controls without returning to the report screen
- Return to the Case Report screen

---

## Screen 8: Underwriting Decision

**Purpose:** Captures the officer's formal decision on the loan application based on the analysis. Creates the official record of action taken and closes the active review loop.

**What it shows:**
- Case summary bar at the top
- The Overall Fraud Confidence Score from the analysis, shown as a read-only reference
- A decision selection with clear options:
  - Approve (Low risk, proceed with loan)
  - Approve with Conditions (e.g., require video KYC, obtain additional document)
  - Escalate for Senior Review
  - Reject (Document fraud suspected)
  - Request Re-submission (Specific documents need replacement)
- A conditions / comments text field that becomes mandatory if "Approve with Conditions" or "Request Re-submission" is selected
- A system-suggested action shown at the top of the decision panel, pulled from the Intelligent Underwriting Insights (e.g., "System recommends: Video KYC before approval"), displayed as a suggestion, not a constraint
- Confirmation checkbox: "I confirm this decision is based on my professional review of the analysis and supporting documents"
- A "Submit Decision" button

**What the user can do:**
- Select a decision
- Enter conditions or reasons (required for conditional approvals and rejections)
- Review the system's suggested action before making their call
- Submit the final decision
- Navigate back to the Case Report to re-review before submitting

---

## Screen 9: Case Detail — Post Decision (Read-Only Summary)

**Purpose:** Provides a permanent, read-only record of a completed case for reference, audit, and compliance purposes. Accessible from the dashboard by clicking on any case with a recorded decision.

**What it shows:**
- Full applicant and loan details
- All uploaded documents listed with their individual sub-scores
- The complete set of anomaly insights from the analysis
- The Overall Fraud Confidence Score
- The decision recorded, who recorded it, and the timestamp
- Any conditions or notes entered by the officer
- The document hash and audit log entry reference (the mock blockchain record from Layer 7)

**What the user can do:**
- View all case information in read-only mode
- Download the full case report as a PDF
- Flag the case for internal review or compliance team attention
- Cannot modify the decision or re-run analysis on a completed case

---

## Screen 10: Audit Trail

**Purpose:** Gives officers and compliance teams a searchable log of all verifications run through the system. Satisfies regulatory and internal audit requirements. Corresponds to Layer 7 of the product.

**What it shows:**
- A chronological table of all cases processed, with columns for: Case ID, Applicant Name, Date Processed, Fraud Score, Decision, Officer, Document Hash (truncated), and Audit Log ID
- Each row is a tamper-evident entry — hash and timestamp recorded at the time of analysis
- A search and filter bar at the top: filter by date range, officer name, risk level, or decision outcome

**What the user can do:**
- Search and filter the audit log
- Click any entry to open the read-only Case Detail screen (Screen 9)
- Export the audit log as a CSV or PDF for compliance reporting
- Cannot edit, delete, or alter any entry

---

## Screen 11: Admin Panel — User Management

**Purpose:** Allows the bank's system administrator to provision and manage officer accounts. Keeps access control internal to the bank without a public-facing registration flow.

**What it shows:**
- A list of all registered users: name, employee ID, role, branch, account status (active/inactive), last login
- An "Add Officer" button
- An edit option per user row

**What the admin can do:**
- Create new officer accounts by entering name, employee ID, email, branch, and role
- Deactivate or reactivate accounts
- Reset a user's password
- View login history per user
- Cannot view or access case-level fraud reports (separation of access concerns)

---

## Screen 12: Settings & Integrations

**Purpose:** Houses system-level configuration. In the MVP this is primarily informational, showing the integration status with external registries that DocVerify is architected to connect with.

**What it shows:**
- Integration status panel: CERSAI, ROC, and State Land Record APIs shown as connected (mock/test), pending, or disconnected
- Current model version and last updated date
- Notification preferences: how and when the officer wants to be notified when a case analysis is complete (email, in-app, or both)
- Officer's own profile details: name, branch, contact

**What the user can do:**
- Update their notification preferences
- Update their profile details (name, contact)
- View integration statuses (read-only in MVP — configuration handled at infrastructure level)

---

## Screen Sequence Summary

```
Login (1)
  → Dashboard (2)
    → New Case Creation (3)
      → Document Upload (4)
        → Analysis in Progress (5)
          → Case Analysis Report (6)
            → Document Viewer (7)  [launched from Report, returns to Report]
            → Underwriting Decision (8)
              → Case Detail / Post-Decision Summary (9)
    → Audit Trail (10)            [accessible from nav at any time]
    → Admin Panel (11)            [admin role only, accessible from nav]
    → Settings (12)               [accessible from nav at any time]
```

---

## Screens Not Needed in MVP

- Applicant-facing portal (loan applicants interact with the bank's existing interface; DocVerify is a back-office tool)
- Verifiable credential wallet (planned Phase 2)
- Real-time registry API configuration UI (backend configuration, not a user screen)
- Billing or subscription screens (internal bank tool, not SaaS in MVP)
