"""NOTAM API client module with rate limiting and inheritance support."""
import requests
import time
import random
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
from src.config import Config
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-20s | %(filename)-15s | %(funcName)-15s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class BaseNotamClient(ABC):
    """
    Abstract base class for NOTAM API clients.
    Allows for future implementations with different authentication methods.
    """
    
    def __init__(self):
        self.config = Config()
        self.session = requests.Session()
        self._setup_authentication()
    
    @abstractmethod
    def _setup_authentication(self):
        """Setup authentication headers. Override in subclasses."""
        pass
    
    @abstractmethod
    def _build_request(self, airport_code: str) -> tuple[str, dict, dict]:
        """
        Build the API request parameters.
        
        Returns:
            Tuple of (url, headers, payload/params)
        """
        pass
    
    @abstractmethod
    def _parse_response(self, response_data: any) -> List[Dict]:
        """Parse the API response into standard format."""
        pass
    
    def fetch_notams_for_airport(self, airport_code: str) -> List[Dict]:
        """
        Fetch NOTAMs for a specific airport with error handling.
        
        Args:
            airport_code: ICAO airport code
            
        Returns:
            List of NOTAM dictionaries
        """
        try:
            url, headers, data = self._build_request(airport_code)
            
            # Make request (POST or GET depending on implementation)
            if data and isinstance(data, dict) and 'designatorsForLocation' in data:
                response = self.session.post(url, data=data, headers=headers, timeout=30)
            else:
                response = self.session.get(url, params=data, headers=headers, timeout=30)
            
            response.raise_for_status()
            
            response_data = response.json()
            return self._parse_response(response_data)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error(f"Rate limited for {airport_code}. Consider increasing delays.")
            else:
                logger.error(f"HTTP error fetching NOTAMs for {airport_code}: {e}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching NOTAMs for {airport_code}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error processing {airport_code}: {e}")
            return []
    
    def fetch_all_notams(self) -> List[Dict]:
        """
        Fetch NOTAMs for all configured airports with natural rate limiting.
        
        Returns:
            List of all NOTAM dictionaries
        """
        all_notams = []
        total_airports = len(self.config.AIRPORTS)
        
        logger.info(f"Fetching NOTAMs for {total_airports} airport(s)")
        
        for idx, airport_code in enumerate(self.config.AIRPORTS, 1):
            airport_code = airport_code.strip()
            
            logger.info(f"[{idx}/{total_airports}] Fetching NOTAMs for {airport_code}")
            notams = self.fetch_notams_for_airport(airport_code)
            
            if notams:
                all_notams.extend(notams)
                logger.info(f"  → Retrieved {len(notams)} NOTAM(s)")
            else:
                logger.warning(f"  → No NOTAMs retrieved")
            
            # Add natural delay between requests (except for last one)
            if idx < total_airports:
                delay = random.uniform(
                    self.config.MIN_REQUEST_DELAY, 
                    self.config.MAX_REQUEST_DELAY
                )
                logger.debug(f"  → Waiting {delay:.2f}s before next request")
                time.sleep(delay)
        
        logger.info(f"Fetched {len(all_notams)} total NOTAM(s) from {total_airports} airport(s)")
        return all_notams


class FAANotamClient(BaseNotamClient):
    """
    NOTAM client for FAA public endpoint (no authentication).
    This is a 'hack' using the public website endpoint.
    """
    
    def _setup_authentication(self):
        """No authentication required for FAA public endpoint."""
        pass
    
    def _build_request(self, airport_code: str) -> tuple[str, dict, dict]:
        """
        Build request for FAA endpoint.
        
        Returns:
            Tuple of (url, headers, payload)
        """
        url = self.config.NOTAM_API_URL
        
        # Headers to mimic browser behavior
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        # Payload structure expected by FAA endpoint
        payload = {
            "searchType": 0,
            "designatorsForLocation": airport_code,
            "notamsOnly": True,
            "latLong": "",
            "radius": "10"
        }
        
        return url, headers, payload
    
    def _parse_response(self, response_data: any) -> List[Dict]:
        """
        Parse FAA API response.
        
        Expected format: List of dictionaries with fields like:
        - facilityDesignator, notamNumber, airportName
        - issueDate, startDate, endDate
        - icaoMessage, status, etc.
        """
        if isinstance(response_data, list):
            return response_data
        elif isinstance(response_data, dict):
            # Some APIs wrap the list in a data field
            return response_data.get('items', []) or response_data.get('data', [])
        else:
            logger.warning(f"Unexpected response format: {type(response_data)}")
            return []


class AuthenticatedNotamClient(BaseNotamClient):
    """
    NOTAM client for APIs requiring token authentication.
    Use with access to a proper API with credentials.
    """
    
    def _setup_authentication(self):
        """Setup Bearer token authentication."""
        if self.config.NOTAM_API_KEY:
            self.session.headers.update({
                'Authorization': f'Bearer {self.config.NOTAM_API_KEY}'
            })
    
    def _build_request(self, airport_code: str) -> tuple[str, dict, dict]:
        """
        Build request for authenticated API.
        Adjust this based on your specific API requirements.
        """
        url = f"{self.config.NOTAM_API_URL}?locations={airport_code}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        params = {
            "format": "json",
            "icao": airport_code
        }
        
        return url, headers, params
    
    def _parse_response(self, response_data: any) -> List[Dict]:
        """Parse authenticated API response."""
        if isinstance(response_data, list):
            return response_data
        elif isinstance(response_data, dict):
            return response_data.get('notams', []) or response_data.get('items', [])
        return []


# Factory function to get the appropriate client
def get_notam_client() -> BaseNotamClient:
    """
    Factory function to instantiate the appropriate NOTAM client.
    
    Returns:
        Instance of appropriate NotamClient subclass
    """
    config = Config()
    
    # Determine which client to use based on configuration
    if config.NOTAM_API_KEY:
        logger.info("Using authenticated NOTAM client")
        return AuthenticatedNotamClient()
    else:
        logger.info("Using FAA public endpoint client (no authentication)")
        return FAANotamClient()