#!/usr/bin/env python3
"""Script to download and load OurAirports CSV."""
import argparse
import sys
import logging
import os
from src.aerodrome_repository import AerodromeRepository
from src.database import NotamDatabase
from src.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Load aerodrome data')
    parser.add_argument('--download', action='store_true', 
                       help='Download CSV from OurAirports')
    parser.add_argument('--csv', type=str, 
                       help='Path to CSV file (default: from config)')
    parser.add_argument('--force', action='store_true',
                       help='Force download even if file exists')
    
    args = parser.parse_args()
    
    config = Config()
    db = NotamDatabase(config.DATABASE_PATH)
    repo = AerodromeRepository(db)
    
    csv_path = args.csv or config.AIRPORTS_CSV_PATH
    
    if args.download:
        if os.path.exists(csv_path) and not args.force:
            logger.info(f"CSV already exists at {csv_path} (use --force to overwrite)")
            sys.exit(0)
        
        logger.info(f"Downloading to {csv_path}")
        success = repo.download_csv(csv_path)
        if not success:
            sys.exit(1)
    
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        logger.info("Use --download to download it first")
        sys.exit(1)
    
    logger.info(f"Loading from {csv_path}")
    count = repo.load_from_csv(csv_path)
    logger.info(f"Loaded {count} aerodromes")
    
    # Show stats
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM aerodromes")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM aerodromes WHERE source='ourairports'")
        ourairports = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM aerodromes WHERE source='notam_inference'")
        inferred = cursor.fetchone()[0]
    
    logger.info(f"Total in database: {total} ({ourairports} from OurAirports, {inferred} inferred)")


if __name__ == '__main__':
    main()