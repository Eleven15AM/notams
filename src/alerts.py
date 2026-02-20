"""Alerting module for ntfy integration."""
import requests
import logging
from typing import Optional

from src.models.notam import Notam
from src.config import Config

logger = logging.getLogger(__name__)


class NtfyAlerter:
    """
    Sends push notifications via ntfy.sh for high-priority NOTAMs.
    Only fires when NTFY_URL is configured.
    """
    
    def __init__(self):
        self.config = Config()
        self.url = self.config.NTFY_URL
        self.min_score = self.config.NTFY_MIN_SCORE
    
    def should_alert(self, notam: Notam) -> bool:
        """
        Determine if a NOTAM should trigger an alert.
        
        Args:
            notam: Notam instance
            
        Returns:
            True if score >= threshold
        """
        if not self.url:
            return False
        
        # Don't alert on CANCEL type unless very high priority
        if notam.notam_type.value == "CANCEL" and notam.priority_score < 80:
            return False
        
        return notam.priority_score >= self.min_score
    
    def _get_priority(self, score: int) -> str:
        """Map score to ntfy priority."""
        if score >= 80:
            return "urgent"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "default"
        else:
            return "low"
    
    def _get_tags(self, notam: Notam) -> list:
        """Generate tags for ntfy message."""
        tags = []
        
        if notam.is_closure:
            tags.append("warning")
        if notam.is_drone_related:
            tags.append("airplane")  # or "drone" but airplane is standard
        if notam.is_restriction:
            tags.append("no_entry")
        if notam.is_permanent:
            tags.append("heavy_plus_sign")
        
        return tags
    
    def send(self, notam: Notam) -> bool:
        """
        Send alert for a NOTAM.
        
        Args:
            notam: Notam instance
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.url:
            logger.warning("NTFY_URL not configured, skipping alert")
            return False
        
        if not self.should_alert(notam):
            logger.debug(f"NOTAM {notam.notam_id} score {notam.priority_score} below threshold {self.min_score}")
            return False
        
        # Build message
        title = f"{notam.notam_id} — {notam.airport_code or notam.location or 'Unknown'}"
        if notam.airport_name:
            title += f" ({notam.airport_name})"
        
        # Sanitize title for HTTP headers (must be Latin-1)
        # Replace em dash with hyphen, remove other non-Latin-1 chars
        title_sanitized = title.encode('latin-1', errors='ignore').decode('latin-1')
        
        body = notam.summary()
        
        headers = {
            "Title": title_sanitized,
            "Priority": self._get_priority(notam.priority_score),
            "Tags": ",".join(self._get_tags(notam))
        }
        
        try:
            response = requests.post(
                self.url,
                data=body.encode('utf-8'),  # Body can be UTF-8
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            logger.info(f"Alert sent for {notam.notam_id} (score: {notam.priority_score})")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send ntfy alert: {e}")
            return False