"""CLI for database migration and admin seeding.

Usage:
    python -m app.cli seed-admin
"""

import argparse
import sys

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_sessionmaker
from app.services.auth_service import seed_admin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-admin", help="Create or promote the initial admin user from env vars")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("cli")

    if args.cmd == "seed-admin":
        with get_sessionmaker()() as db:
            user, created = seed_admin(db, settings)
            log.info("admin_ready", email=user.email, created=created)
    return 0


if __name__ == "__main__":
    sys.exit(main())
