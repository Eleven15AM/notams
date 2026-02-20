"""Configuration module for NOTAM system."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""
    
    # Logging level
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Software Version
    VERSION = os.getenv('VERSION','v0.0.0')

    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', '/app/data/notam.db')
    
    # NOTAM API
    NOTAM_API_URL = os.getenv('NOTAM_API_URL', 'https://notams.aim.faa.gov/notamSearch/search')
    NOTAM_API_KEY = os.getenv('NOTAM_API_KEY', '')
    
    # Airports to monitor (ICAO codes) - now optional if SEARCH_TERMS is set
    AIRPORTS = [a.strip() for a in os.getenv('AIRPORTS', '').split(',') if a.strip()]
    
    # Free-text search terms
    SEARCH_TERMS = [t.strip() for t in os.getenv('SEARCH_TERMS', '').split(',') if t.strip()]
    
    # Update interval
    UPDATE_INTERVAL_SECONDS = int(os.getenv('UPDATE_INTERVAL_SECONDS', '3600'))
    
    # Request rate limiting (to appear natural)
    MIN_REQUEST_DELAY = float(os.getenv('MIN_REQUEST_DELAY', '2'))
    MAX_REQUEST_DELAY = float(os.getenv('MAX_REQUEST_DELAY', '5'))
    
    # Drone detection keywords
    DRONE_KEYWORDS = [k.strip().lower() for k in os.getenv('DRONE_KEYWORDS', 'drone,UAS,unmanned,RPAS').split(',') if k.strip()]
    
    # Weight for drone-related closures - KEEP for backward compatibility
    DRONE_WEIGHT = 10
    NORMAL_WEIGHT = 1
    
    # Alert settings
    NTFY_URL = os.getenv('NTFY_URL', '')
    NTFY_DIGEST_INTERVAL = int(os.getenv('NTFY_DIGEST_INTERVAL', '3600'))  # Default 1 hour
    NTFY_MIN_SCORE = int(os.getenv('NTFY_MIN_SCORE', '80'))  # Only include high-priority
    NTFY_MAX_DIGEST_ITEMS = int(os.getenv('NTFY_MAX_DIGEST_ITEMS', '10'))  # Max items in digest
    
    # Aerodrome data
    AIRPORTS_CSV_PATH = os.getenv('AIRPORTS_CSV_PATH', '/app/data/airports.csv')
    
    # Purge settings
    PURGE_EXPIRED_AFTER_DAYS = int(os.getenv('PURGE_EXPIRED_AFTER_DAYS', '30'))
    PURGE_CANCELLED_AFTER_DAYS = int(os.getenv('PURGE_CANCELLED_AFTER_DAYS', '7'))
    
    # Priority score thresholds
    CLOSURE_SCORE = int(os.getenv('CLOSURE_SCORE', '50'))
    DRONE_SCORE = int(os.getenv('DRONE_SCORE', '30'))
    RESTRICTION_SCORE = int(os.getenv('RESTRICTION_SCORE', '20'))
    
    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.AIRPORTS and not cls.SEARCH_TERMS:
            raise ValueError("Either AIRPORTS or SEARCH_TERMS configuration is required")
        if not cls.NOTAM_API_URL:
            raise ValueError("NOTAM_API_URL configuration is required")
        if cls.VERSION == "v0.0.0":
            raise ValueError("Software Version is default")
        return True