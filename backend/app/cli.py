"""CLI for database migration, admin seeding, demo seeding, and sample dataset loading.

Usage:
    python -m app.cli seed-admin
    python -m app.cli seed-demo
    python -m app.cli load-sample-dataset
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.models import AnalysisRun, BusinessProfile, Dataset, Role, User
from app.db.session import get_sessionmaker
from app.ingestion.loader import persist_cleaned_dataset
from app.ingestion.reader import RawUploadFile, read_upload
from app.ingestion.validator import validate_and_clean
from app.services import analysis_service
from app.services.auth_service import seed_admin
from app.services.dataset_service import ingest_upload
from app.worker.runner import process_next_analysis_job

BUNDLED_SAMPLE_PATH = Path(__file__).resolve().parent / "sample_data" / "01_Healthcare.xlsx"
REPO_SAMPLE_PATH = Path(__file__).resolve().parents[2] / "data" / "01_Healthcare.xlsx"
DEFAULT_SAMPLE_PATH = BUNDLED_SAMPLE_PATH if BUNDLED_SAMPLE_PATH.exists() else REPO_SAMPLE_PATH


def seed_demo_accounts_and_data(db, settings: Settings, workbook_path: Path) -> None:
    """Idempotently seed the 3 demo role accounts, datasets, and verified 6-agent reports."""
    demo_specs = (
        ("admin@mediops.example", "Admin#MediOps2026!", Role.ADMIN, "MediOps Healthcare (Admin)"),
        (
            "e2e.manager@mediops.example",
            "Sunrise#Ward99!Ops",
            Role.MANAGER,
            "MediOps Healthcare (May-Oct 2026)",
        ),
        (
            "audit.analyst@mediops.example",
            "Analyst#MediOps2026!",
            Role.ANALYST,
            "Analyst Permitted Dataset (May-Oct 2026)",
        ),
    )

    cleaned = None
    if workbook_path.exists():
        frames, _ = read_upload(
            [RawUploadFile(filename=workbook_path.name, content=workbook_path.read_bytes())]
        )
        cleaned = validate_and_clean(frames)

    for email, pwd, role, ds_name in demo_specs:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(pwd),
                role=role,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        profile = db.scalar(select(BusinessProfile).where(BusinessProfile.user_id == user.id))
        if profile is None:
            db.add(
                BusinessProfile(
                    user_id=user.id,
                    company_name="Sunrise Multispeciality Hospital",
                    industry="Healthcare",
                    team_size=250,
                    business_goals=(
                        "Reduce outpatient wait times below 35 minutes, curb the 9% no-show rate, "
                        "and align department expenses with invoiced revenue."
                    ),
                )
            )
            db.commit()

        if cleaned is not None:
            ds = db.scalar(select(Dataset).where(Dataset.owner_id == user.id))
            if ds is None:
                ds = persist_cleaned_dataset(
                    db,
                    owner_id=user.id,
                    name=ds_name,
                    source_filename="01_Healthcare.xlsx",
                    cleaned=cleaned,
                )
            run = db.scalar(select(AnalysisRun).where(AnalysisRun.dataset_id == ds.id))
            if run is None:
                orig_role = user.role
                if orig_role == Role.ANALYST:
                    user.role = Role.MANAGER
                    db.commit()
                analysis_service.enqueue_analysis(db, user, ds.id)
                process_next_analysis_job(db, settings)
                if orig_role == Role.ANALYST:
                    user.role = Role.ANALYST
                    db.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-admin", help="Create or promote the initial admin user from env vars")
    demo_p = sub.add_parser(
        "seed-demo", help="Idempotently seed demo Manager/Admin/Analyst accounts and sample dataset"
    )
    demo_p.add_argument("--path", type=Path, default=DEFAULT_SAMPLE_PATH)
    load_p = sub.add_parser(
        "load-sample-dataset", help="Load data/01_Healthcare.xlsx for the admin user"
    )
    load_p.add_argument("--path", type=Path, default=DEFAULT_SAMPLE_PATH)
    load_p.add_argument("--name", default="Hospital Operations (May-Oct 2026)")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("cli")

    with get_sessionmaker()() as db:
        if args.cmd == "seed-admin":
            user, created = seed_admin(db, settings)
            log.info("admin_ready", email=user.email, created=created)
        elif args.cmd == "seed-demo":
            if settings.admin_email and settings.admin_password.get_secret_value():
                seed_admin(db, settings)
            seed_demo_accounts_and_data(db, settings, args.path)
            log.info("demo_accounts_and_data_ready")
        elif args.cmd == "load-sample-dataset":
            user, _ = seed_admin(db, settings)
            raw = RawUploadFile(filename=args.path.name, content=args.path.read_bytes())
            dataset = ingest_upload(db, settings, owner=user, name=args.name, files=[raw])
            log.info("sample_dataset_loaded", dataset_id=str(dataset.id), name=dataset.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
