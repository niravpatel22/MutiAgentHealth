"""Tests for /api/v1/reports, PDF generation, and Human-in-the-Loop (HITL) /api/v1/recommendations."""

from functools import lru_cache
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Role
from app.ingestion.loader import persist_cleaned_dataset
from app.ingestion.reader import RawUploadFile, read_upload
from app.ingestion.validator import CleanedDataset, validate_and_clean
from app.services import analysis_service, auth_service
from app.worker.runner import process_next_analysis_job

WORKBOOK_PATH = Path(__file__).resolve().parents[2] / "data" / "01_Healthcare.xlsx"
SAMPLE_PDF_PATH = Path(__file__).resolve().parents[2] / "docs" / "sample_report.pdf"


@lru_cache(maxsize=1)
def _cached_cleaned() -> CleanedDataset:
    frames, _ = read_upload(
        [RawUploadFile(filename="01_Healthcare.xlsx", content=WORKBOOK_PATH.read_bytes())]
    )
    return validate_and_clean(frames)


def test_reports_pdf_and_hitl_approvals_workflow(
    client: TestClient, db_session: Session, test_settings: Settings
) -> None:
    mgr = auth_service.register_user(
        db_session, "mgr@careops.example", "Sunrise#Ward99!Ops", role=Role.MANAGER
    )
    other_mgr = auth_service.register_user(
        db_session, "other@careops.example", "Sunrise#Ward99!Ops", role=Role.MANAGER
    )
    analyst = auth_service.register_user(
        db_session, "analyst@careops.example", "Sunrise#Ward99!Ops", role=Role.ANALYST
    )
    admin = auth_service.register_user(
        db_session, "adm@careops.example", "Sunrise#Ward99!Ops", role=Role.ADMIN
    )

    ds = persist_cleaned_dataset(
        db_session,
        owner_id=mgr.id,
        name="Hospital Operations (May-Oct 2026)",
        source_filename="01_Healthcare.xlsx",
        cleaned=_cached_cleaned(),
    )
    analysis_service.enqueue_analysis(db_session, mgr, ds.id)
    processed = process_next_analysis_job(db_session, test_settings)
    assert processed is not None

    def tok(email: str) -> str:
        return client.post(
            "/api/v1/auth/login", json={"email": email, "password": "Sunrise#Ward99!Ops"}
        ).json()["access_token"]

    h_mgr = {"Authorization": f"Bearer {tok(mgr.email)}"}
    h_other = {"Authorization": f"Bearer {tok(other_mgr.email)}"}
    h_analyst = {"Authorization": f"Bearer {tok(analyst.email)}"}
    h_admin = {"Authorization": f"Bearer {tok(admin.email)}"}

    # 1. List reports: manager sees 1, other_mgr sees 0, admin sees 1
    rep_list = client.get("/api/v1/reports", headers=h_mgr)
    assert rep_list.status_code == 200
    assert rep_list.json()["total"] == 1
    report_id = rep_list.json()["items"][0]["id"]
    assert client.get("/api/v1/reports", headers=h_other).json()["total"] == 0
    assert client.get("/api/v1/reports", headers=h_admin).json()["total"] == 1

    # 2. Report detail contains all 8 sections, verification, and recommendations
    rep_detail = client.get(f"/api/v1/reports/{report_id}", headers=h_mgr)
    assert rep_detail.status_code == 200
    body = rep_detail.json()
    assert body["verdict"] == "approved"
    assert len(body["content"]["sections"]) == 8
    assert body["verification"]["deterministic"]["is_valid"] is True
    assert len(body["recommendations"]) == 3

    # IDOR check: other_mgr gets 404 on report detail and PDF
    assert client.get(f"/api/v1/reports/{report_id}", headers=h_other).status_code == 404
    assert client.get(f"/api/v1/reports/{report_id}/pdf", headers=h_other).status_code == 404

    # 3.HITL Recommendations: list, detail, analyst forbidden (403), manager approve & reject
    recs_res = client.get("/api/v1/recommendations?status=pending_approval", headers=h_mgr)
    assert recs_res.status_code == 200
    assert recs_res.json()["total"] == 3
    rec1_id = recs_res.json()["items"][0]["id"]
    rec2_id = recs_res.json()["items"][1]["id"]

    # Analyst cannot decide (403)
    forbid = client.post(
        f"/api/v1/recommendations/{rec1_id}/decision",
        headers=h_analyst,
        json={"decision": "approved", "comment": "Analyst trying to approve"},
    )
    assert forbid.status_code == 403

    # Other manager cannot decide on mgr's recommendation (404 IDOR protection)
    idor_dec = client.post(
        f"/api/v1/recommendations/{rec1_id}/decision",
        headers=h_other,
        json={"decision": "approved", "comment": "IDOR attempt"},
    )
    assert idor_dec.status_code == 404

    # Manager approves rec1 and rejects rec2 with comments
    approved_res = client.post(
        f"/api/v1/recommendations/{rec1_id}/decision",
        headers=h_mgr,
        json={
            "decision": "approved",
            "comment": "Approved by Hospital Operations Manager; PO to be raised manually.",
        },
    )
    assert approved_res.status_code == 200
    approved_body = approved_res.json()
    assert approved_body["status"] == "approved"
    assert approved_body["execution_mode"] == "recorded_decision_only"
    assert len(approved_body["approval_history"]) == 1
    assert approved_body["approval_history"][0]["decision"] == "approved"
    assert "PO to be raised manually" in approved_body["approval_history"][0]["comment"]

    rejected_res = client.post(
        f"/api/v1/recommendations/{rec2_id}/decision",
        headers=h_admin,
        json={
            "decision": "rejected",
            "comment": "Deferred to next quarter pending department roster review.",
        },
    )
    assert rejected_res.status_code == 200
    assert rejected_res.json()["status"] == "rejected"

    # 4. Download reproducible PDF (and write docs/sample_report.pdf if missing)
    pdf_res = client.get(f"/api/v1/reports/{report_id}/pdf", headers=h_mgr)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-")
    assert len(pdf_res.content) > 5000

    SAMPLE_PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE_PDF_PATH.write_bytes(pdf_res.content)
