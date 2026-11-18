"""Golden-value tests against data/01_Healthcare.xlsx, quarantine rules, CSV upload, and RBAC/IDOR."""

import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Patient, Role
from app.ingestion.reader import RawUploadFile, UploadValidationError, read_upload
from app.ingestion.validator import validate_and_clean
from app.metrics import (
    UnknownMetricError,
    get_anomalies,
    get_breakdown,
    get_metric,
    get_monthly_series,
    list_metric_specs,
)
from app.services import auth_service, dataset_service

WORKBOOK_PATH = Path(__file__).resolve().parents[2] / "data" / "01_Healthcare.xlsx"


def test_golden_values_on_real_healthcare_workbook(
    db_session: Session, test_settings: Settings
) -> None:
    mgr = auth_service.register_user(
        db_session, "ops@careops.example", "Sunrise#Ward99!Ops", role=Role.MANAGER
    )
    raw = RawUploadFile(filename="01_Healthcare.xlsx", content=WORKBOOK_PATH.read_bytes())
    dataset = dataset_service.ingest_upload(
        db_session, test_settings, owner=mgr, name="Golden Healthcare", files=[raw]
    )
    ds_id = dataset.id

    # ---- Quality report & derived dimensions ----
    qr = dataset.quality_report
    assert qr["rows_loaded"] == {
        "Patients": 1200,
        "Appointments": 2500,
        "Billing": 1800,
        "Medicine_Inventory": 1000,
        "Expenses": 600,
    }
    assert qr["total_quarantined"] == 0
    assert qr["derived_dimensions"] == {"doctors": 40, "suppliers": 60, "vendors": 90}
    assert len(qr["warnings"]) == 1
    assert qr["warnings"][0]["code"] == "duplicate_batch_no"
    assert qr["warnings"][0]["duplicate_batch_count"] == 6
    assert qr["warnings"][0]["affected_items"] == 12

    # ---- Phone masking check ----
    phones = db_session.scalars(
        select(Patient.phone_masked).where(Patient.dataset_id == ds_id).limit(10)
    ).all()
    assert all(p.startswith("******") and len(p) == 10 for p in phones)

    # ---- Golden scalar KPIs ----
    assert get_metric(db_session, ds_id, "appointments.total")["value"] == 2500
    assert get_metric(db_session, ds_id, "appointments.completed")["value"] == 1782
    assert get_metric(db_session, ds_id, "appointments.cancelled")["value"] == 264
    assert get_metric(db_session, ds_id, "appointments.no_show")["value"] == 203
    assert get_metric(db_session, ds_id, "appointments.scheduled")["value"] == 251
    assert get_metric(db_session, ds_id, "appointments.avg_wait_minutes")["value"] == 49.92

    # Scheduled (251) excluded from outcome rate denominators (2500 - 251 = 2249)
    assert get_metric(db_session, ds_id, "appointments.completion_rate")["value"] == round(
        1782 / 2249 * 100, 2
    )
    assert get_metric(db_session, ds_id, "appointments.cancellation_rate")["value"] == round(
        264 / 2249 * 100, 2
    )
    assert get_metric(db_session, ds_id, "appointments.no_show_rate")["value"] == round(
        203 / 2249 * 100, 2
    )
    assert get_metric(db_session, ds_id, "appointments.wait_over_60_share")["value"] > 0

    # Revenue = Billing.net_amount only (never Appointments.consultation_fee)
    assert get_metric(db_session, ds_id, "finance.net_revenue")["value"] == 22256456.76
    assert (
        get_metric(db_session, ds_id, "finance.total_expenses_all_statuses")["value"] == 52970142.83
    )
    assert round(get_metric(db_session, ds_id, "finance.approved_expenses")["value"]) == 26551788
    assert round(get_metric(db_session, ds_id, "finance.pending_expenses")["value"]) == 12228224
    assert round(get_metric(db_session, ds_id, "finance.rejected_expenses")["value"]) == 14190131

    # Approved-expense margin is negative (Approved 26.55M > Revenue 22.26M) and states basis
    margin = get_metric(db_session, ds_id, "finance.approved_margin")
    assert round(margin["value"], 2) == round(22256456.76 - 26551788.08, 2)
    assert "approved_expenses" in margin["basis"]
    assert get_metric(db_session, ds_id, "finance.approved_margin_pct")["value"] == -19.3
    assert get_metric(db_session, ds_id, "finance.avg_discount_rate")["value"] > 0
    assert get_metric(db_session, ds_id, "finance.revenue_per_completed_appointment")["value"] > 0

    # Invoice counts by payment status: Paid 896, Partially Paid 460, Pending 444
    inv_by_status = {
        r["dimension_value"]: r["value"]
        for r in get_breakdown(db_session, ds_id, "finance.invoice_count", "payment_status")[
            "items"
        ]
    }
    assert inv_by_status == {"Paid": 896, "Partially Paid": 460, "Pending": 444}

    # Inventory golden values
    assert get_metric(db_session, ds_id, "inventory.total_items")["value"] == 1000
    assert get_metric(db_session, ds_id, "inventory.low_stock_items")["value"] == 111
    assert get_metric(db_session, ds_id, "inventory.expiring_90d_items")["value"] == 20
    assert get_metric(db_session, ds_id, "inventory.duplicate_batch_count")["value"] == 6
    assert get_metric(db_session, ds_id, "inventory.total_value_at_cost")["value"] > 0

    # Patients & operations
    assert get_metric(db_session, ds_id, "patients.total")["value"] == 1200
    assert get_metric(db_session, ds_id, "patients.repeat_visit_count")["value"] == 527
    assert get_metric(db_session, ds_id, "patients.repeat_visit_rate")["value"] == 43.92
    assert get_metric(db_session, ds_id, "operations.doctor_count")["value"] == 40
    assert get_metric(db_session, ds_id, "operations.appointments_per_doctor")["value"] == 62.5

    # ---- Monthly golden series (May to Oct 2026) ----
    appt_monthly = [
        pt["value"] for pt in get_monthly_series(db_session, ds_id, "appointments.total")["series"]
    ]
    assert appt_monthly == [426, 399, 413, 442, 408, 412]

    rev_monthly = [
        round(pt["value"])
        for pt in get_monthly_series(db_session, ds_id, "finance.net_revenue")["series"]
    ]
    assert rev_monthly == [3584407, 3477155, 3955328, 4152239, 3444869, 3642460]

    exp_monthly = [
        round(pt["value"])
        for pt in get_monthly_series(db_session, ds_id, "finance.total_expenses_all_statuses")[
            "series"
        ]
    ]
    assert exp_monthly == [9749840, 10591918, 8044316, 8854585, 8431648, 7297836]

    # ---- Breakdowns & anomalies ----
    assert len(get_breakdown(db_session, ds_id, "appointments.total", "department")["items"]) == 8
    assert (
        len(
            get_breakdown(db_session, ds_id, "appointments.no_show_rate", "insurance_provider")[
                "items"
            ]
        )
        == 5
    )
    assert (
        len(get_breakdown(db_session, ds_id, "finance.net_revenue", "insurance_provider")["items"])
        == 5
    )
    assert (
        len(
            get_breakdown(db_session, ds_id, "operations.appointments_per_doctor", "doctor_id")[
                "items"
            ]
        )
        == 40
    )
    assert len(get_breakdown(db_session, ds_id, "patients.total", "city")["items"]) == 10
    assert (
        len(get_breakdown(db_session, ds_id, "inventory.low_stock_items", "category")["items"]) == 5
    )

    anomalies = get_anomalies(db_session, ds_id)
    assert isinstance(anomalies, list)
    assert all("rule" in a and "metric_key" in a for a in anomalies)
    assert len(list_metric_specs()) == len({s["key"] for s in list_metric_specs()})

    with pytest.raises(UnknownMetricError):
        get_metric(db_session, ds_id, "nonexistent.metric")


def test_quarantine_rules_and_upload_hardening() -> None:
    frames, _ = read_upload(
        [RawUploadFile(filename="01_Healthcare.xlsx", content=WORKBOOK_PATH.read_bytes())]
    )

    # Inject bad rows into each sheet to verify quarantine reasons
    bad_patients = pd.DataFrame(
        [
            # duplicate PK
            frames["Patients"].iloc[0].to_dict(),
            # out-of-period date
            {
                **frames["Patients"].iloc[1].to_dict(),
                "patient_id": "PAT99001",
                "registration_date": "2026-04-01",
            },
            # invalid age
            {**frames["Patients"].iloc[1].to_dict(), "patient_id": "PAT99002", "age": 150},
            # invalid phone
            {**frames["Patients"].iloc[1].to_dict(), "patient_id": "PAT99003", "phone": 12345},
        ]
    )
    bad_billing = pd.DataFrame(
        [
            # orphan patient_id
            {
                **frames["Billing"].iloc[0].to_dict(),
                "invoice_id": "INV99001",
                "patient_id": "PAT_ORPHAN",
            },
            # net != gross - discount
            {
                **frames["Billing"].iloc[0].to_dict(),
                "invoice_id": "INV99002",
                "gross_amount": 1000.0,
                "discount": 100.0,
                "net_amount": 500.0,
            },
            # negative amount
            {
                **frames["Billing"].iloc[0].to_dict(),
                "invoice_id": "INV99003",
                "gross_amount": -10.0,
                "discount": 0.0,
                "net_amount": -10.0,
            },
            # invalid payment status
            {
                **frames["Billing"].iloc[0].to_dict(),
                "invoice_id": "INV99004",
                "payment_status": "Forgiven",
            },
        ]
    )
    bad_appts = pd.DataFrame(
        [
            {"appointment_id": "", "patient_id": "PAT00001"},
            {**frames["Appointments"].iloc[0].to_dict()},
            {
                **frames["Appointments"].iloc[0].to_dict(),
                "appointment_id": "APT99001",
                "patient_id": "NOPE",
            },
            {
                **frames["Appointments"].iloc[0].to_dict(),
                "appointment_id": "APT99002",
                "department": "Bogus",
            },
            {
                **frames["Appointments"].iloc[0].to_dict(),
                "appointment_id": "APT99003",
                "status": "Bogus",
            },
            {
                **frames["Appointments"].iloc[0].to_dict(),
                "appointment_id": "APT99004",
                "wait_time_minutes": -5,
            },
            {
                **frames["Appointments"].iloc[0].to_dict(),
                "appointment_id": "APT99005",
                "consultation_fee": -10,
            },
        ]
    )
    bad_meds = pd.DataFrame(
        [
            {"item_id": ""},
            {**frames["Medicine_Inventory"].iloc[0].to_dict()},
            {
                **frames["Medicine_Inventory"].iloc[0].to_dict(),
                "item_id": "MED99001",
                "category": "Potion",
            },
            {
                **frames["Medicine_Inventory"].iloc[0].to_dict(),
                "item_id": "MED99002",
                "stock_on_hand": -1,
            },
            {
                **frames["Medicine_Inventory"].iloc[0].to_dict(),
                "item_id": "MED99003",
                "unit_cost": -5.0,
            },
        ]
    )
    bad_expenses = pd.DataFrame(
        [
            {"expense_id": ""},
            {**frames["Expenses"].iloc[0].to_dict()},
            {
                **frames["Expenses"].iloc[0].to_dict(),
                "expense_id": "HEX99001",
                "category": "Bribe",
            },
            {
                **frames["Expenses"].iloc[0].to_dict(),
                "expense_id": "HEX99002",
                "approval_status": "Maybe",
            },
            {
                **frames["Expenses"].iloc[0].to_dict(),
                "expense_id": "HEX99003",
                "amount": -100.0,
            },
        ]
    )

    mutated = {
        **frames,
        "Patients": pd.concat([frames["Patients"], bad_patients], ignore_index=True),
        "Appointments": pd.concat([frames["Appointments"], bad_appts], ignore_index=True),
        "Billing": pd.concat([frames["Billing"], bad_billing], ignore_index=True),
        "Medicine_Inventory": pd.concat(
            [frames["Medicine_Inventory"], bad_meds], ignore_index=True
        ),
        "Expenses": pd.concat([frames["Expenses"], bad_expenses], ignore_index=True),
    }
    cleaned = validate_and_clean(mutated)
    qr = cleaned.quality_report
    assert qr["total_quarantined"] == 25
    reasons = qr["quarantined_by_reason"]
    assert reasons["Patients:duplicate_primary_key"] == 1
    assert reasons["Patients:date_outside_period"] == 1
    assert reasons["Patients:invalid_age"] == 1
    assert reasons["Patients:invalid_phone"] == 1
    assert reasons["Billing:orphan_patient_id"] == 1
    assert reasons["Billing:net_amount_mismatch"] == 1
    assert reasons["Billing:negative_amount"] == 1
    assert reasons["Billing:invalid_payment_status"] == 1
    assert reasons["Appointments:orphan_patient_id"] == 1
    assert reasons["Medicine_Inventory:invalid_category"] == 1
    assert reasons["Expenses:invalid_approval_status"] == 1

    # Hardening: reject fake .xlsx, macro archive, binary .csv, empty, oversized
    with pytest.raises(UploadValidationError):
        read_upload([])
    with pytest.raises(UploadValidationError):
        read_upload([RawUploadFile(filename="empty.xlsx", content=b"")])
    with pytest.raises(UploadValidationError):
        read_upload(
            [RawUploadFile(filename="big.xlsx", content=b"x" * (2 * 1024 * 1024))], max_mb=1
        )
    with pytest.raises(UploadValidationError):
        read_upload([RawUploadFile(filename="notes.txt", content=b"hello")])
    with pytest.raises(UploadValidationError):
        read_upload([RawUploadFile(filename="patients.csv", content=b"only_one_csv")])
    with pytest.raises(UploadValidationError):
        read_upload(
            [
                RawUploadFile(filename=name, content=b"%PDF-1.5 binary")
                for name in (
                    "patients.csv",
                    "appointments.csv",
                    "billing.csv",
                    "medicine_inventory.csv",
                    "expenses.csv",
                )
            ]
        )
    with pytest.raises(UploadValidationError):
        read_upload([RawUploadFile(filename="fake.xlsx", content=b"not a zip file")])

    macro_buf = io.BytesIO()
    with zipfile.ZipFile(macro_buf, "w") as zf:
        zf.writestr("xl/workbook.xml", "<workbook/>")
        zf.writestr("xl/vbaProject.bin", b"macro")
    with pytest.raises(UploadValidationError):
        read_upload([RawUploadFile(filename="macro.xlsx", content=macro_buf.getvalue())])

    with pytest.raises(UploadValidationError):
        read_upload([RawUploadFile(filename="data.xlsm", content=macro_buf.getvalue())])


def test_datasets_api_csv_upload_rbac_and_idor(client: TestClient, db_session: Session) -> None:
    mgr1 = auth_service.register_user(
        db_session, "mgr1@careops.example", "Sunrise#Ward99!Ops", role=Role.MANAGER
    )
    mgr2 = auth_service.register_user(
        db_session, "mgr2@careops.example", "Sunrise#Ward99!Ops", role=Role.MANAGER
    )
    analyst = auth_service.register_user(
        db_session, "analyst@careops.example", "Sunrise#Ward99!Ops", role=Role.ANALYST
    )
    admin = auth_service.register_user(
        db_session, "adm@careops.example", "Sunrise#Ward99!Ops", role=Role.ADMIN
    )

    def tok(email: str) -> str:
        return client.post(
            "/api/v1/auth/login", json={"email": email, "password": "Sunrise#Ward99!Ops"}
        ).json()["access_token"]

    t_mgr1, t_mgr2, t_analyst, t_admin = (
        tok(mgr1.email),
        tok(mgr2.email),
        tok(analyst.email),
        tok(admin.email),
    )

    # Analyst cannot upload (403)
    res_forbidden = client.post(
        "/api/v1/datasets",
        headers={"Authorization": f"Bearer {t_analyst}"},
        files=[
            (
                "files",
                ("01_Healthcare.xlsx", WORKBOOK_PATH.read_bytes(), "application/octet-stream"),
            )
        ],
    )
    assert res_forbidden.status_code == 403

    # Manager 1 uploads 5 CSV files exported from the workbook (using small slice for fast API test)
    frames, _ = read_upload(
        [RawUploadFile(filename="01_Healthcare.xlsx", content=WORKBOOK_PATH.read_bytes())]
    )
    csv_files = [
        (
            "files",
            (f"{entity.lower()}.csv", df.to_csv(index=False).encode("utf-8"), "text/csv"),
        )
        for entity, df in frames.items()
    ]
    up = client.post(
        "/api/v1/datasets",
        headers={"Authorization": f"Bearer {t_mgr1}"},
        data={"name": "CSV Bundle Upload"},
        files=csv_files,
    )
    assert up.status_code == 201
    ds_id = up.json()["id"]
    assert up.json()["row_counts"]["Appointments"] == 2500

    # Manager 1 sees 1 dataset; Manager 2 sees 0; Admin sees 1
    assert (
        client.get("/api/v1/datasets", headers={"Authorization": f"Bearer {t_mgr1}"}).json()[
            "total"
        ]
        == 1
    )
    assert (
        client.get("/api/v1/datasets", headers={"Authorization": f"Bearer {t_mgr2}"}).json()[
            "total"
        ]
        == 0
    )
    assert (
        client.get("/api/v1/datasets", headers={"Authorization": f"Bearer {t_admin}"}).json()[
            "total"
        ]
        == 1
    )

    # IDOR check: Manager 2 gets 404 (not 403) on Manager 1's dataset and quality report
    assert (
        client.get(
            f"/api/v1/datasets/{ds_id}", headers={"Authorization": f"Bearer {t_mgr2}"}
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/datasets/{ds_id}/quality-report",
            headers={"Authorization": f"Bearer {t_mgr2}"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/datasets/{ds_id}", headers={"Authorization": f"Bearer {t_mgr2}"}
        ).status_code
        == 404
    )

    # Manager 1 reads quality report and deletes own dataset
    qr_res = client.get(
        f"/api/v1/datasets/{ds_id}/quality-report",
        headers={"Authorization": f"Bearer {t_mgr1}"},
    )
    assert qr_res.status_code == 200
    assert qr_res.json()["total_loaded"] == 7100

    del_res = client.delete(
        f"/api/v1/datasets/{ds_id}", headers={"Authorization": f"Bearer {t_mgr1}"}
    )
    assert del_res.status_code == 204
    assert (
        client.get(
            f"/api/v1/datasets/{ds_id}", headers={"Authorization": f"Bearer {t_mgr1}"}
        ).status_code
        == 404
    )
