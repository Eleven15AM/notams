"""Main application module."""
import logging
import time
import sys
from src.config import Config
from src.database import NotamDatabase
from src.notam_client import get_notam_client
from src.parser import NotamParser

# Configure logging from environment
log_level = Config.LOG_LEVEL
logging.basicConfig(
    level=getattr(logging, log_level.upper(), logging.INFO),
    format="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-20s | %(filename)-15s | %(funcName)-15s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class NotamMonitor:
    """Main application class for monitoring NOTAMs."""
    
    def __init__(self):
        """Initialize the NOTAM monitor."""
        self.config = Config()
        self.config.validate()
        
        self.db = NotamDatabase(self.config.DATABASE_PATH)
        self.client = get_notam_client()
        self.parser = NotamParser()
        
        logger.info("=" * 80)
        logger.info("NOTAM Monitor initialized")
        logger.info(f"Software Version: {self.config.VERSION}")
        logger.info(f"API Endpoint: {self.config.NOTAM_API_URL}")
        logger.info(f"Monitoring {len(self.config.AIRPORTS)} airport(s)")
        logger.info(f"Database: {self.config.DATABASE_PATH}")
        logger.info(f"Request delay: {self.config.MIN_REQUEST_DELAY}-{self.config.MAX_REQUEST_DELAY}s")
        logger.info(f"Drone keywords: {', '.join(self.config.DRONE_KEYWORDS[:5])}...")
        logger.info("=" * 80)
    
    def process_notams(self) -> tuple[int, int]:
        """
        Fetch and process NOTAMs.
        
        Returns:
            Tuple of (processed_count, closure_count)
        """
        logger.info("Fetching NOTAMs from API...")
        
        # Fetch NOTAMs
        notams = self.client.fetch_all_notams()
        
        if not notams:
            logger.warning("No NOTAMs retrieved from API")
            return 0, 0
        
        logger.info(f"Retrieved {len(notams)} NOTAM(s), parsing for closures...")
        
        # Process each NOTAM
        processed_count = 0
        closure_count = 0
        
        for notam in notams:
            try:
                closure_data = self.parser.parse_notam(notam)
                
                if closure_data:
                    closure_count += 1
                    row_id = self.db.insert_closure(closure_data)
                    
                    if row_id:  # Only count if actually inserted (not duplicate)
                        processed_count += 1
                        
                        log_msg = (
                            f"Inserted: {closure_data['notam_id']} | "
                            f"{closure_data['airport_code']} ({closure_data.get('airport_name', 'N/A')}) | "
                            f"Reason: {closure_data['reason'][:60]}"
                        )
                        
                        if closure_data['is_drone_related']:
                            log_msg += " [ DRONE ACTIVITY]"
                        
                        logger.info(log_msg)
                    
            except Exception as e:
                logger.error(f"Error processing NOTAM: {e}", exc_info=True)
        
        logger.info(
            f"Processing complete: {closure_count} closure(s) found, "
            f"{processed_count} new record(s) inserted"
        )
        return processed_count, closure_count
    
    def run_once(self):
        """Run a single update cycle."""
        logger.info("=" * 80)
        logger.info("Starting NOTAM update cycle")
        logger.info("=" * 80)
        
        start_time = time.time()
        processed, closures = self.process_notams()
        elapsed = time.time() - start_time
        
        # Display statistics
        stats = self.db.get_statistics()
        logger.info("=" * 80)
        logger.info("Database Statistics:")
        logger.info(f"  Total closures in DB: {stats['total_closures']}")
        logger.info(f"  Active closures: {stats['active_closures']}")
        logger.info(f"  Today's closures: {stats['todays_closures']}")
        logger.info(f"  Drone-related (all): {stats['drone_closures']}")
        logger.info(f"  Drone-related (active): {stats['active_drone_closures']}")
        logger.info(f"  Cycle time: {elapsed:.2f}s")
        logger.info("=" * 80)
        logger.info("Update cycle complete")
        logger.info("=" * 80)
        
        return processed
    
    def run_continuous(self):
        """Run continuous monitoring with periodic updates."""
        logger.info("Starting continuous monitoring mode")
        logger.info(f"Update interval: {self.config.UPDATE_INTERVAL_SECONDS}s")
        
        try:
            while True:
                self.run_once()
                logger.info(f"Next update in {self.config.UPDATE_INTERVAL_SECONDS}s...")
                logger.info("")
                time.sleep(self.config.UPDATE_INTERVAL_SECONDS)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Main entry point."""
    # Check if we should run once or continuously
    run_once = '--once' in sys.argv
    
    try:
        monitor = NotamMonitor()
        
        if run_once:
            monitor.run_once()
        else:
            monitor.run_continuous()
    except Exception as e:
        logger.error(f"Failed to start NOTAM monitor: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()