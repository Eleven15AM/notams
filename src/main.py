"""Main application module."""
import logging
import time
import sys
from typing import Optional, Tuple

from src.config import Config
from src.database import NotamDatabase
from src.notam_client import get_notam_client, BaseNotamClient
from src.parser import NotamParser
from src.alerts import NtfyAlerter
from src.models.notam import Notam
from src.alert_digester import AlertDigester

# Configure logging from environment
log_level = Config.LOG_LEVEL
logging.basicConfig(
    level=getattr(logging, log_level.upper(), logging.INFO),
    format="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-20s | %(filename)-15s | %(funcName)-15s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class NotamMonitor:
    """Main application class for monitoring NOTAMs by airport."""
    
    def __init__(self):
        """Initialize the NOTAM monitor."""
        self.config = Config()
        self.config.validate()
        
        self.db = NotamDatabase(self.config.DATABASE_PATH)
        self.client = get_notam_client(mode='airport')
        self.parser = NotamParser()
        self.alerter = NtfyAlerter()
        
        logger.info("=" * 80)
        logger.info("NOTAM Airport Monitor initialized")
        logger.info(f"Software Version: {self.config.VERSION}")
        logger.info(f"API Endpoint: {self.config.NOTAM_API_URL}")
        logger.info(f"Monitoring {len(self.config.AIRPORTS)} airport(s)")
        logger.info(f"Database: {self.config.DATABASE_PATH}")
        logger.info(f"Request delay: {self.config.MIN_REQUEST_DELAY}-{self.config.MAX_REQUEST_DELAY}s")
        logger.info(f"Drone keywords: {', '.join(self.config.DRONE_KEYWORDS[:5])}...")
        logger.info("=" * 80)
    
    def process_notams(self) -> Tuple[int, int, int]:
        """
        Fetch and process NOTAMs.
        
        Returns:
            Tuple of (fetched_count, inserted_count, updated_count)
        """
        logger.info("Fetching NOTAMs from API...")
        
        # Fetch NOTAMs
        notams = self.client.fetch_all_notams()
        
        if not notams:
            logger.warning("No NOTAMs retrieved from API")
            return 0, 0, 0
        
        logger.info(f"Retrieved {len(notams)} NOTAM(s), processing...")
        
        # Process each NOTAM
        inserted = 0
        updated = 0
        
        for raw_notam in notams:
            try:
                notam = self.parser.parse_notam(raw_notam)
                
                if notam:
                    row_id, was_inserted = self.db.upsert_notam(notam)
                    
                    if was_inserted:
                        inserted += 1
                    else:
                        updated += 1
                    
                    # Send alert if needed
                    if self.alerter.should_alert(notam):
                        self.alerter.send(notam)
                    
                    # Log at appropriate level
                    log_msg = (
                        f"{'Inserted' if was_inserted else 'Updated'}: {notam.notam_id} | "
                        f"{notam.airport_code or notam.location or 'N/A'} | "
                        f"Score: {notam.priority_score}"
                    )
                    
                    if notam.is_drone_related:
                        log_msg += " [ DRONE]"
                    if notam.is_closure:
                        log_msg += " [ CLOSURE]"
                    
                    logger.info(log_msg)
                    
            except Exception as e:
                logger.error(f"Error processing NOTAM: {e}", exc_info=True)
        
        # Log search run
        self.db.log_search_run(
            mode='airport',
            airport_codes=self.config.AIRPORTS,
            total_fetched=len(notams),
            new_inserted=inserted,
            updated=updated
        )
        
        logger.info(
            f"Processing complete: {len(notams)} fetched, "
            f"{inserted} new, {updated} updated"
        )
        return len(notams), inserted, updated
    
    def run_once(self):
        """Run a single update cycle."""
        logger.info("=" * 80)
        logger.info("Starting NOTAM update cycle")
        logger.info("=" * 80)
        
        start_time = time.time()
        fetched, inserted, updated = self.process_notams()
        elapsed = time.time() - start_time
        
        # Display statistics
        stats = self.db.get_statistics()
        logger.info("=" * 80)
        logger.info("Database Statistics:")
        logger.info(f"  Total NOTAMs in DB: {stats['total_notams']}")
        logger.info(f"  Active NOTAMs: {stats['active_notams']}")
        logger.info(f"  Closures: {stats['closures']}")
        logger.info(f"  Active closures: {stats['active_closures']}")
        logger.info(f"  Drone-related: {stats['drone_notams']}")
        logger.info(f"  High priority (80+): {stats['high_priority']}")
        logger.info(f"  Cycle time: {elapsed:.2f}s")
        logger.info("=" * 80)
        logger.info("Update cycle complete")
        logger.info("=" * 80)
        
        return inserted
    
    def run_continuous(self):
        """Run continuous monitoring with periodic updates."""
        logger.info("Starting continuous monitoring mode")
        logger.info(f"Update interval: {self.config.UPDATE_INTERVAL_SECONDS}s")
        
        try:
            while True:
                self.run_once()
                
                # Run purge routines occasionally (e.g., once per day)
                # For simplicity, run on every cycle - can be optimized
                self.db.purge_expired(self.config.PURGE_EXPIRED_AFTER_DAYS)
                self.db.purge_cancelled(self.config.PURGE_CANCELLED_AFTER_DAYS)
                
                logger.info(f"Next update in {self.config.UPDATE_INTERVAL_SECONDS}s...")
                logger.info("")
                time.sleep(self.config.UPDATE_INTERVAL_SECONDS)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)


class SearchMonitor:
    """
    Runs free-text NOTAM searches for configured SEARCH_TERMS.
    Mirrors the structure of NotamMonitor but uses FreeTextNotamClient.
    """
    
    def __init__(self):
        """Initialize the search monitor."""
        self.config = Config()
        self.config.validate()
        
        self.db = NotamDatabase(self.config.DATABASE_PATH)
        self.client = get_notam_client(mode='search')
        self.parser = NotamParser()
        self.alerter = NtfyAlerter()
        self.alert_digester = AlertDigester() if self.config.NTFY_URL else None
        
        logger.info("=" * 80)
        logger.info("NOTAM Search Monitor initialized")
        logger.info(f"Software Version: {self.config.VERSION}")
        logger.info(f"API Endpoint: {self.config.NOTAM_API_URL}")
        logger.info(f"Search terms: {', '.join(self.config.SEARCH_TERMS)}")
        logger.info(f"Database: {self.config.DATABASE_PATH}")
        logger.info(f"Request delay: {self.config.MIN_REQUEST_DELAY}-{self.config.MAX_REQUEST_DELAY}s")
        logger.info(f"Drone keywords: {', '.join(self.config.DRONE_KEYWORDS[:5])}...")
        logger.info("=" * 80)
    
    def process_searches(self) -> Tuple[int, int, int]:
        """
        Fetch and process NOTAMs for all search terms.
        
        Returns:
            Tuple of (fetched_count, inserted_count, updated_count)
        """
        logger.info("Fetching NOTAMs via free-text search...")
        
        # Fetch NOTAMs
        notams = self.client.fetch_all_notams()
        
        if not notams:
            logger.warning("No NOTAMs retrieved from API")
            return 0, 0, 0
        
        logger.info(f"Retrieved {len(notams)} NOTAM(s), processing...")
        
        # Process each NOTAM
        inserted = 0
        updated = 0
        
        for raw_notam in notams:
            try:
                notam_obj = self.parser.parse_notam(raw_notam)
                
                if notam_obj:
                    row_id, was_inserted = self.db.upsert_notam(notam_obj)
                    
                    if was_inserted:
                        inserted += 1
                    else:
                        updated += 1

                    # Add to digest queue instead of sending immediately
                    if self.alert_digester:
                        self.alert_digester.add(notam_obj)
                    
                    # Log at appropriate level
                    log_msg = (
                        f"{'Inserted' if was_inserted else 'Updated'}: {notam_obj.notam_id} | "
                        f"{notam_obj.airport_code or notam_obj.location or 'N/A'} | "
                        f"Term: {notam_obj.search_term or 'N/A'} | "
                        f"Score: {notam_obj.priority_score}"
                    )
                    
                    if notam_obj.is_drone_related:
                        log_msg += " [ DRONE]"
                    if notam_obj.is_closure:
                        log_msg += " [ CLOSURE]"
                    
                    logger.info(log_msg)
                    
            except Exception as e:
                logger.error(f"Error processing NOTAM: {e}", exc_info=True)
        
        # Log search run (multiple terms combined)
        self.db.log_search_run(
            mode='search',
            search_term=','.join(self.config.SEARCH_TERMS),
            total_fetched=len(notams),
            new_inserted=inserted,
            updated=updated
        )
        
        logger.info(
            f"Processing complete: {len(notams)} fetched, "
            f"{inserted} new, {updated} updated"
        )
        return len(notams), inserted, updated
    
    def run_once(self):
        """Run a single update cycle."""
        logger.info("=" * 80)
        logger.info("Starting NOTAM search cycle")
        logger.info("=" * 80)
        
        start_time = time.time()
        fetched, inserted, updated = self.process_searches()
        elapsed = time.time() - start_time
        
        # Display statistics
        stats = self.db.get_statistics()
        logger.info("=" * 80)
        logger.info("Database Statistics:")
        logger.info(f"  Total NOTAMs in DB: {stats['total_notams']}")
        logger.info(f"  Active NOTAMs: {stats['active_notams']}")
        logger.info(f"  Closures: {stats['closures']}")
        logger.info(f"  Active closures: {stats['active_closures']}")
        logger.info(f"  Drone-related: {stats['drone_notams']}")
        logger.info(f"  High priority (80+): {stats['high_priority']}")
        logger.info(f"  Cycle time: {elapsed:.2f}s")
        logger.info("=" * 80)
        logger.info("Search cycle complete")
        logger.info("=" * 80)
        
        return inserted
    
    def run_continuous(self):
        """Run continuous monitoring with periodic updates."""
        logger.info("Starting continuous search mode")
        logger.info(f"Update interval: {self.config.UPDATE_INTERVAL_SECONDS}s")
        
        try:
            while True:
                self.run_once()
                
                # Run purge routines
                self.db.purge_expired(self.config.PURGE_EXPIRED_AFTER_DAYS)
                self.db.purge_cancelled(self.config.PURGE_CANCELLED_AFTER_DAYS)
                self.db.purge_old_search_runs()
                
                logger.info(f"Next update in {self.config.UPDATE_INTERVAL_SECONDS}s...")
                logger.info("")
                time.sleep(self.config.UPDATE_INTERVAL_SECONDS)
                
        except KeyboardInterrupt:
            logger.info("Search stopped by user")
            # Send final digest on shutdown
            if self.alert_digester:
                self.alert_digester.send_immediate()
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NOTAM Monitor')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--mode', choices=['airport', 'search', 'auto'], 
                        default='auto', help='Monitoring mode')
    
    args = parser.parse_args()
    
    try:
        config = Config()
        
        # Determine mode
        if args.mode == 'airport':
            monitor = NotamMonitor()
        elif args.mode == 'search':
            monitor = SearchMonitor()
        else:  # auto
            if config.SEARCH_TERMS:
                monitor = SearchMonitor()
            else:
                monitor = NotamMonitor()
        
        if args.once:
            monitor.run_once()
        else:
            monitor.run_continuous()
            
    except Exception as e:
        logger.error(f"Failed to start NOTAM monitor: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()