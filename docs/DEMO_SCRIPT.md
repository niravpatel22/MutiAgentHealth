# Live Demonstration Script (6 to 8 Minutes) — MediOps Intelligence

**Target duration:** 6–8 minutes
**Dataset:** `data/01_Healthcare.xlsx` (May 1 – Oct 31, 2026, INR)

## Pre-Demo Routine (10 Minutes Before Recording)

1. Wake the live backend (`curl https://<backend-url>/api/v1/ready`) if running on a free tier that sleeps.
2. Confirm three accounts exist (or register during the demo):
   - **Admin:** seeded via `ADMIN_EMAIL` / `ADMIN_PASSWORD`
   - **Manager:** registered via `/register` (e.g. `manager@careops.example`)
   - **Analyst:** role set to `analyst` in the Admin Console (e.g. `analyst@careops.example`)

---

## Minute 0:00 – 0:45 · Problem Statement, Registration/Login, & Business Profile

1. Open the live frontend URL on `/login` (or `/register`).
2. Register or sign in as a **Manager** (`manager@careops.example`). Point out:
   - Short-lived 15-minute JWT access token is kept **in memory only** (inspect DevTools `localStorage` to show zero tokens stored there), while the rotating refresh token is in an `httpOnly`, `Secure`, `SameSite=Strict` cookie.
3. Navigate to **Business Profile** (`/profile`) and save:
   - **Company Name:** `Sunrise Multispeciality Hospital`
   - **Industry:** `Healthcare`
   - **Team Size:** `250`
   - **Goals:** `Reduce outpatient wait times below 35 minutes, reduce the 9% no-show rate, and align department expenses with invoiced revenue.`

---

## Minute 0:45 – 1:45 · Dataset Upload & Data Quality Report

1. Navigate to **Datasets** (`/datasets`) and upload `data/01_Healthcare.xlsx`.
2. Open the **Quality Report** panel and highlight:
   - **7,100 rows read and 7,100 rows loaded** across `Patients` (1,200), `Appointments` (2,500), `Billing` (1,800), `Medicine_Inventory` (1,000), and `Expenses` (600), with `0` quarantined rows.
   - **Derived dimension tables:** `40` doctors, `60` suppliers, and `90` vendors derived strictly from IDs without inventing doctor names or specialties.
   - **Quality warning flagged:** `duplicate_batch_no` (`6` batch numbers appear across `12` medicine items — flagged and retained because `item_id` is unique).
   - **PII protection:** patient phone numbers are masked to `******1234` at ingestion and raw patient rows never leave the database.

---

## Minute 1:45 – 3:00 · Live Analytics Dashboard & Dataset Traps

1. Navigate to **Dashboard** (`/dashboard`) and point out that every figure comes live from the deterministic metrics engine (`metrics/registry.py`):
   - **Invoiced Net Revenue:** `₹2.23 Cr` (`₹2,22,56,456.76` from `Billing.net_amount` only — `Appointments.consultation_fee` is never added to avoid double counting).
   - **Approved Expenses:** `₹2.66 Cr` (`₹2,65,51,788.08`), yielding an **Approved-Expense Margin** of `-₹42.95 L` (`-19.30%`).
   - Click **Info** on any KPI card to reveal its exact `definition`, `basis`, and `metric_key`.
2. Walk through the 7 Recharts visualizations and click **Table view** on one chart to show the WCAG 2.1 AA accessible data-table fallback:
   - **Revenue vs Expenses by Month:** shows `Approved`, `Pending` (`₹1.22 Cr` exposure), and `Rejected` (`₹1.42 Cr` non-cost) separately.
   - **Invoiced Value by Payment Status:** `896` Paid, `460` Partially Paid, `444` Pending — labeled strictly as *invoiced value by status*, never "collected cash".
   - **Appointments by Month & Status:** `2,500` total (`1,782` Completed, `251` Scheduled pipeline excluded from outcome rate denominators, `264` Cancelled, `203` No Show), average wait `49.92 min`.
   - **Inventory Risk:** `111` low-stock items and `20` items expiring within 90 days of `2026-10-31`.

---

## Minute 3:00 – 4:30 · Six-Agent CrewAI Execution & Two-Layer Verification

1. Navigate to **New Analysis & Monitor** (`/analyses`) and click **Run New Analysis**.
2. Show the 6-step pipeline polling every 2 seconds:
   - `1. Data Analyst Agent` → `2. Marketing Agent` → `3. Finance Agent` → `4. Operations Agent` → `5. Strategy Agent` → `6. Verification Agent`.
3. Click **View logs** on `Marketing Agent`, `Finance Agent`, and `Strategy Agent` to show:
   - **Inter-agent context chaining (`context_from`):** Marketing, Finance, and Operations receive the Data Analyst's baseline; Strategy receives all four domain outputs; Verification audits Strategy.
   - **Read-only tool calls:** `get_metric`, `get_breakdown`, `get_monthly_series`, `get_anomalies` scoped server-side to `dataset_id`.
4. Explain the **Two-Layer Verification & Revision Loop**:
   - Layer 1 (`verifier.py`) recomputes every cited `metric_key` and scans narrative text for unbacked numbers.
   - Layer 2 (`Verification Agent`) checks qualitative consistency and data limits.
   - If a finding cites an unbacked or mismatched number, the verifier rejects it and triggers up to 2 `Strategy → Verification` revision loops; if it still fails, the report is saved as `REJECTED` with zero pending recommendations.

---

## Minute 4:30 – 5:45 · Verified BI Report, PDF Export, & Human-in-the-Loop Approvals

1. Open **Reports** (`/reports`):
   - Show the `APPROVED` verdict badge, `HIGH` confidence badge, and `18/18` deterministic checks passed.
   - Scroll through the **8 mandatory report sections**.
   - Click any metric evidence chip (e.g. `finance.approved_margin` or `inventory.low_stock_items`) to open the live metric definition inspector.
   - Click **Download PDF** and open the downloaded multi-page executive PDF (`cover`, `KPI baseline table`, `embedded revenue/expense chart`, `8 sections`, `findings`, `HITL table`, and `verification appendix`).
2. Open **Approvals (HITL)** (`/approvals`):
   - Enter a governance comment on the pharmacy replenishment proposal and click **Approve Proposal**.
   - Enter a comment on a second proposal and click **Reject Proposal**.
   - Show the updated status and immutable `Approval History` audit trail (`Recorded Decision Only` — nothing executes automatically).

---

## Minute 5:45 – 7:15 · Grounded AI Chat, History, & Admin Console (Role Check)

1. Open **AI Chat** (`/chat`):
   - Click `"What is our invoiced net revenue and approved-expense margin?"` → show the grounded answer (`INR 22,256,456.76` revenue, `-19.30%` margin) and `cited_metric_keys` chips.
   - Click the trap question `"What is our marketing campaign ROI and ad spend?"` → show the assistant replying honestly: **`"The dataset cannot answer that: no marketing campaign, channel, lead-source, or marketing spend data exists..."`**.
2. Open **History** (`/history`) to show all saved analysis runs, revision counts, verdicts, and one-click PDF retrieval.
3. Sign in as **Admin** and open **Admin Console** (`/admin`):
   - Show user role management (`admin`, `manager`, `analyst`), all organization-wide analyses, and all reports.
   - Briefly switch to (or mention) the **Analyst** account on `/approvals` and `/datasets` to confirm an `analyst` has read-only access and cannot upload datasets or approve recommendations (`403 Forbidden`).
