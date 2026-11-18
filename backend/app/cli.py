"""CLI for database migration, admin seeding, and sample dataset loading.

Usage:
    python -m app.cli seed-admin
    python -m app.cli load-sample-dataset
"""

import argparse
import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_sessionmaker
from app.ingestion.reader import RawUploadFile
from app.services.auth_service import seed_admin
from app.services.dataset_service import ingest_upload

DEFAULT_SAMPLE_PATH = Path(__file__).resolve().parents[2] / "data" / "01_Healthcare.xlsx"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-admin", help="Create or promote the initial admin user from env vars")
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
        elif args.cmd == "load-sample-dataset":
            user, _ = seed_admin(db, settings)
            raw = RawUploadFile(filename=args.path.name, content=args.path.read_bytes())
            dataset = ingest_upload(db, settings, owner=user, name=args.name, files=[raw])
            log.info("sample_dataset_loaded", dataset_id=str(dataset.id), name=dataset.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
