"""Fetch MOLIT world airport data and refresh the local directory tables."""

from __future__ import annotations

import argparse
import logging

from app.db.session import SessionLocal
from app.services.airport_directory import AirportDirectorySynchronizer


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync countries/airports directory")
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    db = SessionLocal()
    try:
        synchronizer = AirportDirectorySynchronizer(db)
        result = synchronizer.run()
        logger.info(
            "Sync complete: %s countries, %s airports (%s skipped)",
            result.country_count,
            result.airport_count,
            result.skipped_airports,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()


