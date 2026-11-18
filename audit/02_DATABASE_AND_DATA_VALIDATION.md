# Phase 2 — Database and Dataset Verification

**Project:** MediOps Intelligence — AI-Powered Hospital Operations & Performance Intelligence
**Dataset Inspected:** `data/01_Healthcare.xlsx` (May 1, 2026 – October 31, 2026, Currency: INR)
**Database Engine:** PostgreSQL `18.7` (`postgresql+psycopg://`)

---

## 1. Workbook & Relational Schema Verification

### 1.1 Excel Workbook Inspection (`data/01_Healthcare.xlsx`)
Inspected using `openpyxl.load_workbook(..., read_only=True, data_only=True)`:

| Sheet Name | Row Count | Columns Verified | Imported Target Table | Status |
|---|---:|---|---|---|
| `Patients` | `1,200` | `patient_id`, `patient_name`, `age`, `gender`, `city`, `phone`, `registration_date`, `insurance_provider` | `patients` (plus derived `age_band`, `registration_month`, `phone_masked`) | **PASS** |
| `Appointments` | `2,500` | `appointment_id`, `patient_id`, `doctor_id`, `department`, `appointment_date`, `appointment_type`, `status`, `wait_time_minutes`, `consultation_fee` | `appointments` + derived `doctors` (`40` unique `doctor_id` rows) | **PASS** |
| `Billing` | `1,800` | `invoice_id`, `patient_id`, `invoice_date`, `service_type`, `gross_amount`, `discount`, `net_amount`, `payment_status`, `payment_mode` | `invoices` | **PASS** |
| `Medicine_Inventory` | `1,000` | `item_id`, `medicine_name`, `batch_no`, `category`, `stock_on_hand`, `reorder_level`, `unit_cost`, `expiry_date`, `supplier_id` | `medicine_items` + derived `suppliers` (`60` unique `supplier_id` rows) | **PASS** |
| `Expenses` | `600` | `expense_id`, `expense_date`, `category`, `department`, `amount`, `vendor`, `approval_status` | `expenses` + derived `vendors` (`90` unique `vendor` rows) | **PASS** |
| `README` | `6` | Metadata sheet (`Field`, `Details`) | Ignored during entity ingestion | **PASS** |
| **Total Entity Rows** | **`7,100`** | All required columns present and typed (`NUMERIC(14,2)` for money, `Date` for dates) | **`7,100` loaded (`0` quarantined)** | **PASS** |

### 1.2 Database Integrity, Isolation, Re-Upload & Rollback Verification

| Check | Verification Method | Actual Result | Status |
|---|---|---|---|
| **Foreign Key Integrity** | Composite FKs (`fk_appointments_patient`, `fk_appointments_doctor`, `fk_invoices_patient`, `fk_medicine_items_supplier`, `fk_expenses_vendor`) enforced in PostgreSQL | `0` orphan rows; invalid FKs injected in `test_quarantine_rules_and_upload_hardening` are quarantined with reason `orphan_patient_id` | **PASS** |
| **Primary Key Uniqueness** | Composite PKs `(dataset_id, <entity_pk>)` across all 8 domain tables | `0` duplicate primary keys; injected duplicate PKs are quarantined with reason `duplicate_primary_key` | **PASS** |
| **PII Masking & Non-Exposure** | Inspected all `1,200` `Patient.phone_masked` rows in PostgreSQL + checked all API & tool schemas | All `1,200` phones match `^\*{6}\d{4}$` (e.g., `******6001`); `patient_name` is never returned by any API endpoint or CrewAI tool | **PASS** |
| **Transactional Upload & Rollback Safety** | Tested invalid uploads (`.xlsm` macro payload, fake zip, binary `.csv`, all-invalid rows) | Failed imports raise `UploadValidationError` (`400`/`422`) and roll back cleanly leaving `0` partial domain rows | **PASS** |
| **Re-Upload & Dataset Ownership Isolation** | Uploaded `01_Healthcare.xlsx` across multiple datasets (`test_golden_values_on_real_healthcare_workbook` + `test_datasets_api_csv_upload_rbac_and_idor`) | Composite `(dataset_id, ...)` keys isolate each upload; cross-manager access returns `404`; deleting a dataset cascades all `7,100` domain rows via `ON DELETE CASCADE` | **PASS** |
| **Fresh Database Migrations** | `alembic upgrade head` (`0001_initial_app` -> `0002_domain_healthcare`) | Executes transactionally without errors | **PASS** |

---

## 2. Verification of the 17 Golden Dataset Figures

Every expected dataset figure from the audit specification was verified directly against PostgreSQL and `backend/app/metrics/registry.py` on `data/01_Healthcare.xlsx`:

| # | Metric Description | Metric Key / Breakdown | Expected Golden Figure | Actual Computed Value | Match / Status |
|---:|---|---|---|---|---|
| 1 | **Patients** | `patients.total` | `1,200` | `1200` | **PASS** |
| 2 | **Appointments** | `appointments.total` | `2,500` | `2500` | **PASS** |
| 3 | **Completed Appointments** | `appointments.completed` | `1,782` | `1782` (`79.24%` of `2,249` non-scheduled) | **PASS** |
| 4 | **Cancelled Appointments** | `appointments.cancelled` | `264` | `264` (`11.74%` of `2,249` non-scheduled) | **PASS** |
| 5 | **No Show Appointments** | `appointments.no_show` | `203` | `203` (`9.03%` of `2,249` non-scheduled) | **PASS** |
| 6 | **Scheduled Appointments** | `appointments.scheduled` | `251` | `251` (pipeline, excluded from outcome rate denominator) | **PASS** |
| 7 | **Average Wait Time** | `appointments.avg_wait_minutes` | `49.92 minutes` | `49.92 minutes` | **PASS** |
| 8 | **Net Invoiced Revenue** | `finance.net_revenue` | `₹22,256,456.76` | `₹22,256,456.76` (`22256456.76`) | **PASS** |
| 9 | **Total Expenses (All Statuses)** | `finance.total_expenses_all_statuses` | `₹52,970,142.83` | `₹52,970,142.83` (`52970142.83`) | **PASS** |
| 10 | **Approved Expenses** | `finance.approved_expenses` | `₹26,551,788` (rounded ₹) | `₹26,551,788.08` (`round() == 26551788`) | **PASS** |
| 11 | **Pending Expenses** | `finance.pending_expenses` | `₹12,228,224` (rounded ₹) | `₹12,228,223.82` (`round() == 12228224`) | **PASS** |
| 12 | **Rejected Expenses** | `finance.rejected_expenses` | `₹14,190,131` (rounded ₹) | `₹14,190,130.93` (`round() == 14190131`) | **PASS** |
| 13 | **Paid Invoices** | `finance.invoice_count` (`payment_status=Paid`) | `896` | `896` (invoiced net value `₹11,207,707.88`) | **PASS** |
| 14 | **Partially Paid Invoices** | `finance.invoice_count` (`payment_status=Partially Paid`) | `460` | `460` (invoiced net value `₹5,500,100.69`) | **PASS** |
| 15 | **Pending Invoices** | `finance.invoice_count` (`payment_status=Pending`) | `444` | `444` (invoiced net value `₹5,548,648.19`) | **PASS** |
| 16 | **Inventory at or below Reorder Level** | `inventory.low_stock_items` (`stock_on_hand <= reorder_level`) | `111` | `111` | **PASS** |
| 17 | **Items Expiring within 90 Days** | `inventory.expiring_90d_items` (`expiry_date <= 2027-01-29` as of `2026-10-31`) | `20` | `20` | **PASS** |

---

## 3. Verification of the 10 Mandatory Business Rules

| Rule # | Business Rule | Implementation & Runtime Evidence | Status |
|---:|---|---|---|
| **1** | Revenue uses `Billing.net_amount` only | `finance.net_revenue` queries `SUM(invoices.net_amount)` (`₹22,256,456.76`), with `basis="invoiced_billing_net_amount_only"` | **PASS** |
| **2** | Appointment consultation fees are not added to revenue | `Appointment.consultation_fee` is never summed into any revenue metric (`definition` explicitly states exclusion to prevent double counting) | **PASS** |
| **3** | Approved, pending and rejected expenses remain separate | Separate metric keys (`finance.approved_expenses`, `finance.pending_expenses`, `finance.rejected_expenses`) and separate stacked/series bars on the dashboard | **PASS** |
| **4** | Rejected expenses are not treated as approved costs | `finance.approved_margin` is computed strictly as `net_revenue - approved_expenses` (`-₹4,295,331.32` / `-19.30%`), excluding `Pending` (`₹12.23M` exposure) and `Rejected` (`₹14.19M` non-cost) | **PASS** |
| **5** | Partially paid invoices are not falsely represented as fully collected | All invoice metrics and charts label `payment_status` strictly as *invoiced value / count by payment status* (`basis="invoiced_billing_net_amount_by_status_no_amount_paid_column"`) and agents/verifier reject claims of collected cash | **PASS** |
| **6** | Marketing ROI is not invented | Marketing Agent, Verifier, and AI Chat explicitly report that no marketing campaign, channel, or spend data exists in `01_Healthcare.xlsx` | **PASS** |
| **7** | Doctor and supplier names are not fabricated | Derived `doctors` (`40`), `suppliers` (`60`), and `vendors` (`90`) tables store only the dataset IDs (`DOC0001`..`DOC0040`, `SUP0001`..`SUP0060`) and primary department without fabricating human names | **PASS** |
| **8** | Inventory consumption and stock-out forecasts are not invented | Operations Agent, Verifier, and AI Chat report only point-in-time reorder risk (`111`), 90-day expiry risk (`20`), and duplicate batches (`6`), explicitly refusing stock-out date forecasts | **PASS** |
| **9** | Scheduled appointments are excluded from completed/no-show outcome denominators | Denominator for `completion_rate` (`79.24%`), `cancellation_rate` (`11.74%`), and `no_show_rate` (`9.03%`) is `2,500 - 251 = 2,249` resolved appointments | **PASS** |
| **10** | Duplicate inventory batch numbers are flagged rather than deleting valid inventory records | All `1,000` `Medicine_Inventory` rows are loaded (`item_id` is unique); the `6` duplicate `batch_no` values (`B14407`, `B35801`, `B40863`, `B46579`, `B90998`, `B96721`) across `12` items are flagged with `is_duplicate_batch=True` and surfaced in `quality_report.warnings` | **PASS** |
