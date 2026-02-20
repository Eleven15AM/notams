"""NOTAM API client module with rate limiting and inheritance support."""
import requests
import time
import random
from typing import List, Dict, Optional, Set
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
    def _build_request(self, **kwargs) -> tuple[str, dict, dict]:
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
    
    def fetch_notams(self, **kwargs) -> List[Dict]:
        """
        Fetch NOTAMs with error handling.
        
        Args:
            **kwargs: Request-specific parameters
            
        Returns:
            List of NOTAM dictionaries
        """
        try:
            url, headers, data = self._build_request(**kwargs)
            
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
                logger.error(f"Rate limited. Consider increasing delays.")
            else:
                logger.error(f"HTTP error fetching NOTAMs: {e}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching NOTAMs: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []
    
    def fetch_all_notams(self) -> List[Dict]:
        """
        Fetch NOTAMs for all configured items (airports or search terms).
        
        Returns:
            List of all NOTAM dictionaries (deduplicated)
        """
        # This should be overridden by subclasses that need special handling
        raise NotImplementedError


class FAANotamClient(BaseNotamClient):
    """
    NOTAM client for FAA public endpoint (no authentication) - Airport search.
    """
    
    def _setup_authentication(self):
        """No authentication required for FAA public endpoint."""
        pass
    
    def _build_request(self, airport_code: str = None, **kwargs) -> tuple[str, dict, dict]:
        """
        Build request for FAA endpoint.
        
        Args:
            airport_code: ICAO airport code
            
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
    
    def fetch_notams_for_airport(self, airport_code: str) -> List[Dict]:
        """Fetch NOTAMs for a specific airport."""
        return self.fetch_notams(airport_code=airport_code)
    
    def fetch_all_notams(self) -> List[Dict]:
        """
        Fetch NOTAMs for all configured airports with natural rate limiting.
        
        Returns:
            List of all NOTAM dictionaries
        """
        all_notams = []
        seen_ids: Set[str] = set()
        total_airports = len(self.config.AIRPORTS)
        
        logger.info(f"Fetching NOTAMs for {total_airports} airport(s)")
        
        for idx, airport_code in enumerate(self.config.AIRPORTS, 1):
            airport_code = airport_code.strip()
            
            logger.info(f"[{idx}/{total_airports}] Fetching NOTAMs for {airport_code}")
            notams = self.fetch_notams_for_airport(airport_code)
            
            if notams:
                # Deduplicate
                new_count = 0
                for notam in notams:
                    notam_id = notam.get('notamNumber')
                    if notam_id and notam_id not in seen_ids:
                        seen_ids.add(notam_id)
                        all_notams.append(notam)
                        new_count += 1
                logger.info(f"  → Retrieved {len(notams)} NOTAM(s), {new_count} new")
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


class FreeTextNotamClient(BaseNotamClient):
    """
    NOTAM client for FAA free-text search endpoint.
    Handles pagination automatically (30 records per page).
    """
    
    def __init__(self):
        super().__init__()
        self.page_size = 30
    
    def _setup_authentication(self):
        """No authentication required for FAA public endpoint."""
        pass
    
    def _build_request(self, search_term: str = None, offset: int = 0, **kwargs) -> tuple[str, dict, dict]:
        """
        Build request for FAA free-text search.
        
        Args:
            search_term: Free text search term
            offset: Pagination offset
            
        Returns:
            Tuple of (url, headers, payload)
        """
        url = self.config.NOTAM_API_URL
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        payload = {
            "searchType": 4,
            "freeFormText": search_term,
            "notamsOnly": False,
            "latLong": "",
            "radius": "10",
            "offset": str(offset)
        }
        
        return url, headers, payload
    
    def _parse_response(self, response_data: any) -> List[Dict]:
        """
        Parse FAA free-text search response.
        
        Expected format:
        {
            "notamList": [...],
            "totalNotamCount": 123,
            "startRecordCount": 1,
            "endRecordCount": 30
        }
        """
        if isinstance(response_data, dict):
            return response_data.get('notamList', [])
        elif isinstance(response_data, list):
            return response_data
        else:
            logger.warning(f"Unexpected response format: {type(response_data)}")
            return []
    
    def search_term(self, term: str) -> List[Dict]:
        """
        Search for NOTAMs by free text term with pagination.
        
        Args:
            term: Search term
            
        Returns:
            List of NOTAM dictionaries
        """
        all_notams = []
        seen_ids: Set[str] = set()
        offset = 0
        page_num = 1
        
        while True:
            logger.info(f"  Searching '{term}' - page {page_num} (offset {offset})")
            
            try:
                url, headers, payload = self._build_request(search_term=term, offset=offset)
                response = self.session.post(url, data=payload, headers=headers, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                notams = data.get('notamList', [])
                total_count = data.get('totalNotamCount', 0)
                start = data.get('startRecordCount', 0)
                end = data.get('endRecordCount', 0)
                
                logger.info(f"    Retrieved {len(notams)} records (total: {total_count}, records {start}-{end})")
                
                # Deduplicate
                new_count = 0
                for notam in notams:
                    notam_id = notam.get('notamNumber')
                    if notam_id and notam_id not in seen_ids:
                        seen_ids.add(notam_id)
                        # Add search term to each NOTAM for tracking
                        notam['_search_term'] = term
                        all_notams.append(notam)
                        new_count += 1
                
                logger.info(f"    {new_count} new, {len(notams) - new_count} duplicates")
                
                # Check if we need another page
                if end >= total_count or not notams:
                    break
                
                offset = end
                page_num += 1
                
                # Rate limiting between pages
                delay = random.uniform(
                    self.config.MIN_REQUEST_DELAY,
                    self.config.MAX_REQUEST_DELAY
                )
                logger.debug(f"  → Waiting {delay:.2f}s before next page")
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Error during pagination: {e}")
                break
        
        return all_notams
    
    def fetch_all_notams(self) -> List[Dict]:
        """
        Fetch NOTAMs for all configured search terms.
        
        Returns:
            List of all NOTAM dictionaries (deduplicated)
        """
        all_notams = []
        seen_ids: Set[str] = set()
        total_terms = len(self.config.SEARCH_TERMS)
        
        logger.info(f"Searching for {total_terms} free-text term(s)")
        
        for idx, term in enumerate(self.config.SEARCH_TERMS, 1):
            term = term.strip()
            if not term:
                continue
            
            logger.info(f"[{idx}/{total_terms}] Searching for: '{term}'")
            notams = self.search_term(term)
            
            # Add to results (already deduplicated within the search)
            all_notams.extend(notams)
            
            # Rate limiting between terms (except last)
            if idx < total_terms:
                delay = random.uniform(
                    self.config.MIN_REQUEST_DELAY,
                    self.config.MAX_REQUEST_DELAY
                )
                logger.debug(f"→ Waiting {delay:.2f}s before next search term")
                time.sleep(delay)
        
        logger.info(f"Total: {len(all_notams)} unique NOTAMs across all search terms")
        return all_notams


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
    
    def _build_request(self, airport_code: str = None, **kwargs) -> tuple[str, dict, dict]:
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
    
    def fetch_all_notams(self) -> List[Dict]:
        """Fetch NOTAMs for all configured airports (fallback to airport mode)."""
        # Fallback to airport mode if no specific implementation
        client = FAANotamClient()
        return client.fetch_all_notams()


# Factory function to get the appropriate client
def get_notam_client(mode: Optional[str] = None) -> BaseNotamClient:
    """
    Factory function to instantiate the appropriate NOTAM client.
    
    Args:
        mode: 'airport' for FAANotamClient, 'search' for FreeTextNotamClient.
              If None, determine from config: if SEARCH_TERMS is set, use search mode.
    
    Returns:
        Instance of appropriate NotamClient subclass
    """
    config = Config()
    
    if mode is not None:
        if mode == 'airport':
            logger.info("Using FAA airport endpoint client (mode=airport)")
            return FAANotamClient()
        elif mode == 'search':
            logger.info("Using FAA free-text search client (mode=search)")
            return FreeTextNotamClient()
    
    # Auto-detect mode
    if config.NOTAM_API_KEY:
        logger.info("Using authenticated NOTAM client")
        return AuthenticatedNotamClient()
    elif config.SEARCH_TERMS:
        logger.info("SEARCH_TERMS detected, using free-text search client")
        return FreeTextNotamClient()
    else:
        logger.info("Using FAA airport endpoint client (AIRPORTS mode)")
        return FAANotamClient()