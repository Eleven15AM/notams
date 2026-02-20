"""Parser module for NOTAM data."""
from typing import Dict, Optional
import logging
from datetime import datetime

from src.config import Config
from src.models.notam import Notam

logger = logging.getLogger(__name__)


class NotamParser:
    """Parses NOTAM data and returns Notam objects."""
    
    def __init__(self):
        self.config = Config()
    
    def parse_notam(self, notam_data: Dict) -> Optional[Notam]:
        """
        Parse a NOTAM entry and return a Notam object.
        
        Args:
            notam_data: Raw NOTAM data dictionary from FAA API
            
        Returns:
            Notam object or None if the record should be skipped
        """
        # Extract search term if present (added by FreeTextNotamClient)
        search_term = notam_data.get('_search_term')
        
        # Skip cancelled or expired NOTAMs
        if notam_data.get('cancelledOrExpired', False) or notam_data.get('status', '').lower() == 'expired':
            logger.debug(f"Skipping cancelled/expired NOTAM: {notam_data.get('notamNumber', '')}")
            return None
        
        # Create Notam object
        try:
            notam = Notam.from_api_dict(notam_data, search_term=search_term)
            return notam
        except Exception as e:
            logger.error(f"Error creating Notam from data: {e}", exc_info=True)
            return None
    
    # Legacy methods - delegate to Notam class for backward compatibility in tests
    def _is_closure_notam(self, text: str) -> bool:
        """Legacy method - creates a dummy Notam to check closure status."""
        if not text:
            return False
        # Create a minimal Notam just to check closure
        dummy_data = {
            'icaoMessage': f"DUMMY NOTAMN\nE) {text}",
            'cancelledOrExpired': False
        }
        try:
            notam = Notam.from_api_dict(dummy_data)
            return notam.is_closure
        except:
            return False
    
    def _is_drone_related(self, text: str) -> bool:
        """Legacy method - creates a dummy Notam to check drone status."""
        if not text:
            return False
        # Create a minimal Notam just to check drone status
        dummy_data = {
            'icaoMessage': f"DUMMY NOTAMN\nE) {text}",
            'cancelledOrExpired': False
        }
        try:
            notam = Notam.from_api_dict(dummy_data)
            return notam.is_drone_related
        except:
            return False
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Legacy method - delegate to Notam's static method and return datetime object."""
        return Notam._parse_faa_date(date_str)