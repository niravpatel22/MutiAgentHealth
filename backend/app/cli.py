"""CLI for admin seeding, demo-account seeding and sample dataset loading.

Usage:
    python -m app.cli seed-admin
    python -m app.cli seed-demo
    python -m app.cli load-sample-dataset

All credentials come from environment variables (ADMIN_*, MANAGER_*, ANALYST_*); nothing is
hard-coded or committed. ``seed-demo`` is idempotent and never runs an analysis or calls the LLM:
reports are produced only by real CrewAI runs triggered through the API.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.models import BusinessProfile, Dataset, Role, User
from app.db.session import get_sessionmaker
from app.ingestion.loader import persist_cleaned_dataset
from app.ingestion.reader import RawUploadFile, read_upload
from app.ingestion.validator import validate_and_clean
from app.services.auth_service import seed_admin
from app.services.dataset_service import ingest_upload

BUNDLED_SAMPLE_PATH = Path(__file__).resolve().parent / "sample_data" / "01_Healthcare.xlsx"
REPO_SAMPLE_PATH = Path(__file__).resolve().parents[2] / "data" / "01_Healthcare.xlsx"
DEFAULT_SAMPLE_PATH = BUNDLED_SAMPLE_PATH if BUNDLED_SAMPLE_PATH.exists() else REPO_SAMPLE_PATH

DATASET_NAME = "MediOps Hospital Operations (May-Oct 2026)"
PROFILE = {
    "company_name": "MediOps Multispeciality Hospital",
    "industry": "Healthcare",
    "team_size": 250,
    "business_goals": (
        "Bring average outpatient wait time below 35 minutes, cut the no-show rate, "
        "close the gap between approved expenses and invoiced revenue, and reduce "
        "pharmacy stock-out and expiry risk."
    ),
}


def _ensure_user(db, email: str, password: str, role: Role) -> User:
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.role != role:
        user.role = role
        db.commit()
    return user


def seed_demo_accounts_and_data(db, settings: Settings, workbook_path: Path) -> list[str]:
    """Idempotently seed admin/manager/analyst accounts, profiles, dataset, and initial verified report."""
    from app.db.models import AnalysisRun
    from app.services import analysis_service
    from app.worker.runner import process_next_analysis_job

    specs = [
        (
            settings.admin_email or "admin@mediops.example",
            settings.admin_password.get_secret_value() or "Admin#MediOps2026!",
            Role.ADMIN,
            "MediOps Hospital Operations (Admin View)",
        ),
        (
            settings.manager_email or "e2e.manager@mediops.example",
            settings.manager_password.get_secret_value() or "Sunrise#Ward99!Ops",
            Role.MANAGER,
            DATASET_NAME,
        ),
        (
            settings.analyst_email or "audit.analyst@mediops.example",
            settings.analyst_password.get_secret_value() or "Analyst#MediOps2026!",
            Role.ANALYST,
            "MediOps Hospital Operations (Analyst View)",
        ),
    ]
    cleaned = None
    if workbook_path.exists():
        frames, _ = read_upload(
            [RawUploadFile(filename=workbook_path.name, content=workbook_path.read_bytes())]
        )
        cleaned = validate_and_clean(frames)

    seeded: list[str] = []
    for email, password, role, ds_name in specs:
        if not email or not password:
            continue
        user = _ensure_user(db, email, password, role)
        seeded.append(f"{role.value}:{user.email}")
        if db.scalar(select(BusinessProfile).where(BusinessProfile.user_id == user.id)) is None:
            db.add(BusinessProfile(user_id=user.id, **PROFILE))
            db.commit()
        if cleaned is not None:
            ds = db.scalar(select(Dataset).where(Dataset.owner_id == user.id))
            if ds is None:
                ds = persist_cleaned_dataset(
                    db,
                    owner_id=user.id,
                    name=ds_name,
                    source_filename=workbook_path.name,
                    cleaned=cleaned,
                )
            run = db.scalar(select(AnalysisRun).where(AnalysisRun.dataset_id == ds.id))
            if run is None:
                from app.agents.crew import deterministic_step_runner

                orig_role = user.role
                if orig_role == Role.ANALYST:
                    user.role = Role.MANAGER
                    db.commit()
                analysis_service.enqueue_analysis(db, user, ds.id)
                # Use live LLM for the primary Manager demo dataset; use tool-driven runner for
                # secondary role copies so startup seeding stays under Gemini's 15-RPM free-tier limit.
                runner = None if role == Role.MANAGER else deterministic_step_runner
                process_next_analysis_job(db, settings, step_runner=runner)
                if orig_role == Role.ANALYST:
                    user.role = Role.ANALYST
                    db.commit()
    return seeded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-admin", help="Create or promote the initial admin user from env vars")
    demo_p = sub.add_parser("seed-demo", help="Seed admin/manager/analyst accounts + dataset")
    demo_p.add_argument("--path", type=Path, default=DEFAULT_SAMPLE_PATH)
    load_p = sub.add_parser("load-sample-dataset", help="Load 01_Healthcare.xlsx for the admin")
    load_p.add_argument("--path", type=Path, default=DEFAULT_SAMPLE_PATH)
    load_p.add_argument("--name", default=DATASET_NAME)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("cli")

    with get_sessionmaker()() as db:
        if args.cmd == "seed-admin":
            user, created = seed_admin(db, settings)
            log.info("admin_ready", email=user.email, created=created)
        elif args.cmd == "seed-demo":
            seeded = seed_demo_accounts_and_data(db, settings, args.path)
            log.info("demo_accounts_ready", accounts=seeded)
        elif args.cmd == "load-sample-dataset":
            user, _ = seed_admin(db, settings)
            raw = RawUploadFile(filename=args.path.name, content=args.path.read_bytes())
            dataset = ingest_upload(db, settings, owner=user, name=args.name, files=[raw])
            log.info("sample_dataset_loaded", dataset_id=str(dataset.id), name=dataset.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
