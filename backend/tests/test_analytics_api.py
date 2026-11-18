"""Tests for /api/v1/datasets/{id}/kpis, /trends, and /breakdowns/{dimension}."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Role
from app.ingestion.reader import RawUploadFile
from app.services import auth_service, dataset_service

WORKBOOK_PATH = Path(__file__).resolve().parents[2] / "data" / "01_Healthcare.xlsx"


def test_analytics_kpis_trends_and_breakdowns(
    client: TestClient, db_session: Session, test_settings: Settings
) -> None:
    mgr = auth_service.register_user(
        db_session, "mgr@careops.example", "Sunrise#Ward99!Ops", role=Role.MANAGER
    )
    other = auth_service.register_user(
        db_session, "other@careops.example", "Sunrise#Ward99!Ops", role=Role.MANAGER
    )
    raw = RawUploadFile(filename="01_Healthcare.xlsx", content=WORKBOOK_PATH.read_bytes())
    ds = dataset_service.ingest_upload(
        db_session, test_settings, owner=mgr, name="Hospital Ops", files=[raw]
    )

    mgr_tok = client.post(
        "/api/v1/auth/login", json={"email": mgr.email, "password": "Sunrise#Ward99!Ops"}
    ).json()["access_token"]
    other_tok = client.post(
        "/api/v1/auth/login", json={"email": other.email, "password": "Sunrise#Ward99!Ops"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {mgr_tok}"}

    # IDOR check: other manager gets 404 on KPIs, trends, and breakdowns
    for path in (
        f"/api/v1/datasets/{ds.id}/kpis",
        f"/api/v1/datasets/{ds.id}/trends",
        f"/api/v1/datasets/{ds.id}/breakdowns/department",
    ):
        assert client.get(path, headers={"Authorization": f"Bearer {other_tok}"}).status_code == 404

    # Full-range KPIs
    kpis = client.get(f"/api/v1/datasets/{ds.id}/kpis", headers=headers)
    assert kpis.status_code == 200
    cards = {c["key"]: c for c in kpis.json()["cards"]}
    assert len(cards) == 9
    assert cards["finance.net_revenue"]["value"] == 22256456.76
    assert cards["finance.net_revenue"]["mom_change_pct"] is not None
    assert cards["appointments.total"]["value"] == 2500
    assert cards["inventory.low_stock_items"]["value"] == 111
    assert cards["inventory.expiring_90d_items"]["value"] == 20

    # Month-filtered KPIs (May to Jul 2026: 426 + 399 + 413 = 1238 appointments)
    filtered = client.get(f"/api/v1/datasets/{ds.id}/kpis?from=2026-05&to=2026-07", headers=headers)
    assert filtered.status_code == 200
    f_cards = {c["key"]: c for c in filtered.json()["cards"]}
    assert f_cards["appointments.total"]["value"] == 426 + 399 + 413

    # Invalid month filter -> 400
    assert client.get(f"/api/v1/datasets/{ds.id}/kpis?from=bad", headers=headers).status_code == 400
    assert (
        client.get(
            f"/api/v1/datasets/{ds.id}/kpis?from=2026-09&to=2026-06", headers=headers
        ).status_code
        == 400
    )

    # Trends
    trends = client.get(f"/api/v1/datasets/{ds.id}/trends", headers=headers)
    assert trends.status_code == 200
    tdata = trends.json()
    assert len(tdata["revenue_vs_expenses"]) == 6
    assert len(tdata["appointments_by_status"]) == 6
    assert [p["total"] for p in tdata["appointments_by_status"]] == [426, 399, 413, 442, 408, 412]

    # Breakdowns for every dashboard dimension
    for dim, expected_len in (
        ("department", 8),
        ("payment_status", 3),
        ("city", 10),
        ("insurance_provider", 5),
        ("age_band", 5),
        ("category", 5),
        ("doctor_id", 40),
        ("service_type", 6),
        ("approval_status", 3),
    ):
        res = client.get(f"/api/v1/datasets/{ds.id}/breakdowns/{dim}", headers=headers)
        assert res.status_code == 200, dim
        assert len(res.json()["items"]) == expected_len, dim

    assert (
        client.get(f"/api/v1/datasets/{ds.id}/breakdowns/unknown", headers=headers).status_code
        == 400
    )
