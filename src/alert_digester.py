"""Digest alert system for batching NOTAM notifications."""
import time
import logging
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests

from src.models.notam import Notam
from src.config import Config

logger = logging.getLogger(__name__)


class AlertDigester:
    """
    Accumulates high-priority NOTAMs and sends periodic digests.
    Prevents rate limiting by batching notifications.
    """
    
    def __init__(self):
        self.config = Config()
        self.url = self.config.NTFY_URL
        self.interval = self.config.NTFY_DIGEST_INTERVAL
        self.min_score = self.config.NTFY_MIN_SCORE
        self.max_items = self.config.NTFY_MAX_DIGEST_ITEMS
        
        # Accumulators
        self.notams: List[Notam] = []
        self.stats = defaultdict(int)  # Counts by type
        self.airports = set()  # Unique airports affected
        self.last_send = time.time()
        self.lock = threading.Lock()
        
        # Start background thread if URL is configured
        if self.url:
            self._start_digest_thread()
    
    def add(self, notam: Notam) -> None:
        """
        Add a NOTAM to the digest queue if it meets criteria.
        
        Args:
            notam: Notam to potentially include
        """
        if not self.url:
            return
        
        if notam.priority_score < self.min_score:
            logger.debug(f"NOTAM {notam.notam_id} score {notam.priority_score} below digest threshold")
            return
        
        with self.lock:
            self.notams.append(notam)
            
            # Update stats
            self.stats['total'] += 1
            if notam.is_closure:
                self.stats['closures'] += 1
            if notam.is_drone_related:
                self.stats['drone'] += 1
            if notam.is_restriction:
                self.stats['restrictions'] += 1
            
            # Track unique airports
            if notam.airport_code:
                self.airports.add(notam.airport_code)
            
            logger.debug(f"Added {notam.notam_id} to digest queue (now {len(self.notams)} items)")
    
    def _start_digest_thread(self) -> None:
        """Start background thread that sends periodic digests."""
        def digest_loop():
            while True:
                time.sleep(self.interval)
                try:
                    self._send_digest()
                except Exception as e:
                    logger.error(f"Error sending digest: {e}")
        
        thread = threading.Thread(target=digest_loop, daemon=True)
        thread.start()
        logger.info(f"Alert digester started (interval: {self.interval}s, min score: {self.min_score})")
    
    def _send_digest(self) -> bool:
        """
        Send a digest of accumulated NOTAMs.
        
        Returns:
            True if sent successfully, False otherwise
        """
        with self.lock:
            if not self.notams:
                logger.debug("No NOTAMs to digest")
                return False
            
            # Take snapshot and clear
            notams = self.notams.copy()
            stats = dict(self.stats)
            airports = list(self.airports)
            
            # Reset accumulators
            self.notams.clear()
            self.stats.clear()
            self.airports.clear()
        
        # Sort by priority (highest first)
        notams.sort(key=lambda n: n.priority_score, reverse=True)
        
        # Build digest message
        title = f"NOTAM Digest: {stats.get('total', 0)} new high-priority items"
        
        body_parts = [
            f"📊 **Summary**",
            f"• Total: {stats.get('total', 0)}",
            f"• Closures: {stats.get('closures', 0)}",
            f"• Drone-related: {stats.get('drone', 0)}",
            f"• Restrictions: {stats.get('restrictions', 0)}",
            f"• Airports affected: {len(airports)}",
            "",
            f"⏰ Period: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}",
            "",
        ]
        
        if notams:
            body_parts.append("🔔 **Top Items**")
            
            # Show top N items
            for i, notam in enumerate(notams[:self.max_items], 1):
                airport = notam.airport_code or notam.location or "Unknown"
                flags = []
                if notam.is_closure:
                    flags.append("CLOSURE")
                if notam.is_drone_related:
                    flags.append("DRONE")
                if notam.is_restriction:
                    flags.append("RESTRICTED")
                
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                
                # Truncate body if needed
                body_preview = notam.body.replace('\n', ' ').strip()
                if len(body_preview) > 100:
                    body_preview = body_preview[:100] + "..."
                
                body_parts.append(
                    f"\n{i}. **{notam.notam_id}** - {airport} (Score: {notam.priority_score}){flag_str}\n"
                    f"   {body_preview}"
                )
            
            if len(notams) > self.max_items:
                body_parts.append(f"\n... and {len(notams) - self.max_items} more")
        
        body_parts.append(f"\n[View in NOTAM system]({self.url.replace('/send', '')})")
        
        body = "\n".join(body_parts)
        
        # Sanitize title for headers
        title_sanitized = title.encode('latin-1', errors='ignore').decode('latin-1')
        
        headers = {
            "Title": title_sanitized,
            "Priority": "default",
            "Tags": "bell"
        }
        
        try:
            response = requests.post(
                self.url,
                data=body.encode('utf-8'),
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            logger.info(f"Digest sent: {stats.get('total', 0)} NOTAMs")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send digest: {e}")
            
            # Re-queue the NOTAMs? For simplicity, we'll just log the error
            # In production, you might want to store them for retry
            return False
    
    def send_immediate(self) -> bool:
        """
        Force an immediate digest send (useful for shutdown).
        
        Returns:
            True if sent successfully
        """
        return self._send_digest()