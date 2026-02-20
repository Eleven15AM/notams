"""Aerodrome repository for caching ICAO airport data."""
import csv
import logging
import os
import urllib.request
from datetime import datetime
from typing import Optional, Dict, List, Any
from contextlib import contextmanager

from src.config import Config
from src.database import NotamDatabase
from src.models.notam import Notam

logger = logging.getLogger(__name__)


class AerodromeRepository:
    """
    Caches ICAO aerodrome data in SQLite.
    Primary data source: OurAirports open dataset (CSV, loaded once).
    Falls back to data already seen in NOTAMs if CSV not loaded.
    """
    
    # OurAirports CSV URL
    OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
    
    def __init__(self, db: NotamDatabase):
        """
        Initialize repository.
        
        Args:
            db: Database instance for storage and lookup
        """
        self.db = db
        self.config = Config()
        self._ensure_table()
    
    def _ensure_table(self):
        """Ensure aerodromes table exists."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS aerodromes (
                    icao_code     TEXT PRIMARY KEY,
                    iata_code     TEXT,
                    name          TEXT,
                    type          TEXT,
                    latitude      REAL,
                    longitude     REAL,
                    elevation_ft  INTEGER,
                    continent     TEXT,
                    country_code  TEXT,
                    country_name  TEXT,
                    region        TEXT,
                    municipality  TEXT,
                    gps_code      TEXT,
                    source        TEXT,
                    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Index for faster lookups
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_aerodromes_icao 
                ON aerodromes(icao_code)
            ''')
            
            logger.debug("Aerodromes table ensured")
    
    def get(self, icao_code: str) -> Optional[Dict[str, Any]]:
        """
        Get aerodrome by ICAO code (DB-first lookup).
        
        Args:
            icao_code: ICAO airport code (e.g., 'KATL')
            
        Returns:
            Aerodrome dict or None if not found
        """
        if not icao_code:
            return None
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM aerodromes WHERE icao_code = ?',
                (icao_code.upper(),)
            )
            row = cursor.fetchone()
            
            if row:
                return dict(row)
        
        return None
    
    def load_from_csv(self, csv_path: Optional[str] = None) -> int:
        """
        Bulk load OurAirports CSV.
        
        Args:
            csv_path: Path to CSV file. If None, uses config.AIRPORTS_CSV_PATH.
            
        Returns:
            Number of records loaded
        """
        path = csv_path or self.config.AIRPORTS_CSV_PATH
        
        if not os.path.exists(path):
            logger.warning(f"CSV file not found: {path}")
            return 0
        
        count = 0
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                for row in reader:
                    # Only store airports with ICAO codes
                    ident = row.get('ident', '')
                    if not ident or len(ident) != 4 or not ident.isalpha():
                        continue
                    
                    # Map country code to name (simplified - could use a proper mapping)
                    country_code = row.get('iso_country', '')
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO aerodromes (
                            icao_code, iata_code, name, type,
                            latitude, longitude, elevation_ft,
                            continent, country_code, country_name,
                            region, municipality, gps_code, source,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        ident,
                        row.get('iata_code'),
                        row.get('name'),
                        row.get('type'),
                        self._safe_float(row.get('latitude_deg')),
                        self._safe_float(row.get('longitude_deg')),
                        self._safe_int(row.get('elevation_ft')),
                        row.get('continent'),
                        country_code,
                        self._country_code_to_name(country_code),
                        row.get('iso_region'),
                        row.get('municipality'),
                        row.get('gps_code'),
                        'ourairports',
                        datetime.now().isoformat()
                    ))
                    
                    count += 1
                    
                    if count % 1000 == 0:
                        logger.info(f"Loaded {count} aerodromes...")
        
        logger.info(f"Loaded {count} aerodromes from {path}")
        return count
    
    def infer_from_notam(self, notam: Notam) -> None:
        """
        Store minimal record inferred from NOTAM data when no CSV data exists.
        
        Args:
            notam: Notam instance containing airport info
        """
        icao_code = notam.airport_code
        if not icao_code:
            return
        
        # Check if already exists
        existing = self.get(icao_code)
        if existing:
            return
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO aerodromes (
                    icao_code, name, source, updated_at
                ) VALUES (?, ?, ?, ?)
            ''', (
                icao_code,
                notam.airport_name or f"Airport {icao_code}",
                'notam_inference',
                datetime.now().isoformat()
            ))
            
            logger.debug(f"Inferred aerodrome from NOTAM: {icao_code}")
    
    def enrich_notam(self, notam: Notam) -> Dict[str, Any]:
        """
        Enrich NOTAM with aerodrome data.
        
        Args:
            notam: Notam instance
            
        Returns:
            Aerodrome dict (empty if not found)
        """
        if not notam.airport_code:
            return {}
        
        aerodrome = self.get(notam.airport_code)
        if aerodrome:
            return aerodrome
        
        # Try to infer and store for future
        self.infer_from_notam(notam)
        return {}
    
    @staticmethod
    def download_csv(target_path: str) -> bool:
        """
        Download OurAirports CSV from source.
        
        Args:
            target_path: Where to save the CSV
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            logger.info(f"Downloading OurAirports CSV from {AerodromeRepository.OURAIRPORTS_URL}")
            urllib.request.urlretrieve(AerodromeRepository.OURAIRPORTS_URL, target_path)
            logger.info(f"Downloaded to {target_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download CSV: {e}")
            return False
    
    @staticmethod
    def _safe_float(value: Optional[str]) -> Optional[float]:
        """Convert string to float safely."""
        if not value:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _safe_int(value: Optional[str]) -> Optional[int]:
        """Convert string to int safely."""
        if not value:
            return None
        try:
            return int(float(value))  # Handle "123.0" format
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _country_code_to_name(code: str) -> str:
        """Simple ISO country code to name mapping."""
        # This is a minimal mapping - expand as needed
        mapping = {
            'US': 'United States',
            'CA': 'Canada',
            'GB': 'United Kingdom',
            'FR': 'France',
            'DE': 'Germany',
            'JP': 'Japan',
            'CN': 'China',
            'AU': 'Australia',
            'BR': 'Brazil',
            'ZA': 'South Africa',
            'AE': 'United Arab Emirates',
            'SG': 'Singapore',
            'DK': 'Denmark',
            'NO': 'Norway',
            'SE': 'Sweden',
            'FI': 'Finland',
            'PL': 'Poland',
            'LT': 'Lithuania',
            'EE': 'Estonia',
            'LV': 'Latvia',
            'HU': 'Hungary',
            'CZ': 'Czech Republic',
            'AT': 'Austria',
            'GR': 'Greece',
            'TR': 'Turkey',
            'IL': 'Israel',
            'OM': 'Oman',
            'SA': 'Saudi Arabia',
            'IR': 'Iran',
            'IQ': 'Iraq',
            'KE': 'Kenya',
            'EG': 'Egypt',
            'ET': 'Ethiopia',
            'JO': 'Jordan',
            'BH': 'Bahrain',
            'QA': 'Qatar',
            'BD': 'Bangladesh',
            'NP': 'Nepal',
            'TH': 'Thailand',
            'VN': 'Vietnam',
            'PH': 'Philippines',
            'ID': 'Indonesia',
            'MY': 'Malaysia',
            'NZ': 'New Zealand',
            'MX': 'Mexico',
            'AR': 'Argentina',
            'CO': 'Colombia',
            'CL': 'Chile',
            'PE': 'Peru',
            'UY': 'Uruguay',
            'PY': 'Paraguay',
            'BO': 'Bolivia',
        }
        return mapping.get(code, code)