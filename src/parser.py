"""Parser module for NOTAM data."""
import re
from datetime import datetime
from typing import Dict, Optional
from src.config import Config
import logging

logger = logging.getLogger(__name__)


class NotamParser:
    """Parses NOTAM data and extracts closure information."""
    
    def __init__(self):
        self.config = Config()
    
    def parse_notam(self, notam_data: Dict) -> Optional[Dict]:
        """
        Parse a NOTAM entry and extract closure information.
        
        Args:
            notam_data: Raw NOTAM data dictionary from FAA API
            
        Returns:
            Parsed closure data or None if not a closure NOTAM
        """
        # Extract basic information from FAA API structure
        notam_id = notam_data.get('notamNumber', '')
        airport_code = notam_data.get('facilityDesignator', '') or notam_data.get('icaoId', '')
        airport_name = notam_data.get('airportName', '')
        full_text = notam_data.get('icaoMessage', '')
        status = notam_data.get('status', '')
        
        # Skip cancelled or expired NOTAMs
        if notam_data.get('cancelledOrExpired', False) or status.lower() == 'expired':
            logger.debug(f"Skipping cancelled/expired NOTAM: {notam_id}")
            return None
        
        # Check if this is a closure NOTAM
        if not self._is_closure_notam(full_text):
            return None
        
        # Parse dates
        issue_date = self._parse_date(notam_data.get('issueDate'))
        closure_start = self._parse_date(notam_data.get('startDate'))
        closure_end = self._parse_date(notam_data.get('endDate'))
        
        # Extract reason
        reason = self._extract_reason(full_text)
        
        # Determine if drone-related
        is_drone_related = self._is_drone_related(full_text)
        
        # Set weight
        weight = Config.DRONE_WEIGHT if is_drone_related else Config.NORMAL_WEIGHT
        
        return {
            'notam_id': notam_id,
            'airport_code': airport_code,
            'airport_name': airport_name,
            'issue_date': issue_date,
            'closure_start': closure_start,
            'closure_end': closure_end,
            'reason': reason,
            'full_text': full_text,
            'weight': weight,
            'is_drone_related': is_drone_related
        }
    
    def _is_closure_notam(self, text: str) -> bool:
        """Check if NOTAM indicates a closure."""
        text_lower = text.lower()
        closure_keywords = [
            'closed', 'clsd', 'closure', 'not avbl',
            'unavailable', 'suspended', 'ad clsd',
            'airport closed', 'rwy closed', 'runway closed'
        ]
        return any(keyword in text_lower for keyword in closure_keywords)
    
    # def _is_drone_related(self, text: str) -> bool:
    #     """Check if closure is drone-related."""
    #     text_lower = text.lower()
    #     return any(keyword in text_lower for keyword in self.config.DRONE_KEYWORDS)

    def _is_drone_related(self, text: str) -> bool:
        """Check if closure is drone-related."""
        text_lower = text.lower()    
        for keyword in self.config.DRONE_KEYWORDS:
            # Use word boundaries to match whole words only
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, text_lower):
                logger.info(f"NOTAM flagged as drone-related. Keyword found: '{keyword}'")
                return True
        
        logger.debug("NOTAM not drone-related - no keywords found")
        return False

    def _extract_reason(self, text: str) -> str:
        """Extract the reason for closure from NOTAM text."""
        # Try to extract reason from common patterns
        reason_patterns = [
            r'(?:DUE TO|REASON|BECAUSE OF)\s+([^.\n]+)',
            r'E\)\s*([^.\n]{10,100})',  # Item E) usually contains the reason
            r'CLSD\s+([^.\n]+)',
        ]
        
        for pattern in reason_patterns:
            reason_match = re.search(pattern, text, re.IGNORECASE)
            if reason_match:
                reason = reason_match.group(1).strip()
                if len(reason) > 10:  # Ensure we got something meaningful
                    return reason[:200]
        
        # If no specific reason found, return truncated text
        clean_text = text.replace('\n', ' ').strip()
        return clean_text[:200] + ('...' if len(clean_text) > 200 else '')
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Parse date from FAA API format.
        
        FAA format: "MM/DD/YYYY HHmm" or "PERM"
        Examples: "04/29/2025 0913", "PERM"
        
        Returns:
            ISO format datetime string or None
        """
        if not date_str:
            return None
        
        # Handle permanent NOTAMs
        if isinstance(date_str, str) and date_str.strip().upper() == 'PERM':
            return None
        
        try:
            # Try FAA format: "MM/DD/YYYY HHmm"
            if isinstance(date_str, str) and len(date_str) >= 10:
                # Remove any timezone indicators
                date_str = re.sub(r'\s*(EST|UTC|GMT)$', '', date_str.strip())
                
                parts = date_str.split()
                if len(parts) >= 2:
                    date_part = parts[0]  # MM/DD/YYYY
                    time_part = parts[1]  # HHmm
                    
                    date_components = date_part.split('/')
                    if len(date_components) == 3:
                        month = int(date_components[0])
                        day = int(date_components[1])
                        year = int(date_components[2])
                        
                        # Parse time
                        if len(time_part) >= 4:
                            hour = int(time_part[0:2])
                            minute = int(time_part[2:4])
                        else:
                            hour = 0
                            minute = 0
                        
                        dt = datetime(year, month, day, hour, minute)
                        return dt.isoformat()
        except (ValueError, IndexError, AttributeError) as e:
            logger.warning(f"Could not parse date '{date_str}': {e}")
        
        return None