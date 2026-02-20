#!/usr/bin/env python3
"""Database maintenance CLI."""
import argparse
import sys
import logging
from src.database import NotamDatabase
from src.config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Database maintenance')
    parser.add_argument('--purge-expired', type=int, metavar='DAYS',
                       help='Purge NOTAMs expired more than DAYS ago')
    parser.add_argument('--purge-cancelled', type=int, metavar='DAYS',
                       help='Purge cancelled NOTAMs older than DAYS')
    parser.add_argument('--purge-search-runs', type=int, metavar='DAYS',
                       help='Purge search run logs older than DAYS')
    parser.add_argument('--purge-all', action='store_true',
                       help='Run all purge routines with configured values')
    
    args = parser.parse_args()
    
    config = Config()
    db = NotamDatabase(config.DATABASE_PATH)
    
    if args.purge_all:
        expired = db.purge_expired(config.PURGE_EXPIRED_AFTER_DAYS)
        cancelled = db.purge_cancelled(config.PURGE_CANCELLED_AFTER_DAYS)
        search = db.purge_old_search_runs(90)
        logger.info(f"Purged: {expired} expired, {cancelled} cancelled, {search} search runs")
        
    else:
        if args.purge_expired:
            count = db.purge_expired(args.purge_expired)
            logger.info(f"Purged {count} expired NOTAMs")
        
        if args.purge_cancelled:
            count = db.purge_cancelled(args.purge_cancelled)
            logger.info(f"Purged {count} cancelled NOTAMs")
        
        if args.purge_search_runs:
            count = db.purge_old_search_runs(args.purge_search_runs)
            logger.info(f"Purged {count} search run logs")


if __name__ == '__main__':
    main()