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
    NOTAM_API_URL = os.getenv('NOTAM_API_URL', 'https://notams.aim.faa.gov/notamSearch/search') #mucho hack-o
    NOTAM_API_KEY = os.getenv('NOTAM_API_KEY', '')
    
    # Airports to monitor (ICAO codes)
    AIRPORTS = [a.strip() for a in os.getenv('AIRPORTS', 'EGLL,LFPG,EDDF').split(',') if a.strip()]
    
    # Update interval
    UPDATE_INTERVAL_SECONDS = int(os.getenv('UPDATE_INTERVAL_SECONDS', '3600'))
    
    # Request rate limiting (to appear natural)
    MIN_REQUEST_DELAY = float(os.getenv('MIN_REQUEST_DELAY', '2'))
    MAX_REQUEST_DELAY = float(os.getenv('MAX_REQUEST_DELAY', '5'))
    
    # Drone detection keywords
    DRONE_KEYWORDS = [k.strip().lower() for k in os.getenv('DRONE_KEYWORDS', 'drone,UAS,unmanned,RPAS').split(',') if k.strip()]
    
    # Weight for drone-related closures
    DRONE_WEIGHT = 10
    NORMAL_WEIGHT = 1
    
    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.AIRPORTS:
            raise ValueError("AIRPORTS configuration is required")
        if not cls.NOTAM_API_URL:
            raise ValueError("NOTAM_API_URL configuration is required")
        if cls.VERSION == "v0.0.0":
            raise ValueError("Software Version is default")
        return True