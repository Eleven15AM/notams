"""Database module for storing NOTAM data."""
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from contextlib import contextmanager
import logging

from src.models.notam import Notam, NotamType

logger = logging.getLogger(__name__)


class NotamDatabase:
    """Handles all database operations for NOTAM data."""
    
    def __init__(self, db_path: str):
        """Initialize database connection."""
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_database(self):
        """Create database tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # notams table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notams (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    notam_id            TEXT NOT NULL UNIQUE,
                    series              TEXT,
                    notam_type          TEXT,
                    replaces_notam_id   TEXT,
                    cancels_notam_id    TEXT,
                    fir                 TEXT,
                    q_code              TEXT,
                    q_code_subject      TEXT,
                    q_code_condition    TEXT,
                    traffic             TEXT,
                    purpose             TEXT,
                    scope               TEXT,
                    lower_limit         INTEGER,
                    upper_limit         INTEGER,
                    coordinates         TEXT,
                    latitude            REAL,
                    longitude           REAL,
                    radius_nm           INTEGER,
                    airport_code        TEXT,
                    airport_name        TEXT,
                    location            TEXT,
                    valid_from          DATETIME,
                    valid_to            DATETIME,
                    is_permanent        BOOLEAN DEFAULT 0,
                    schedule            TEXT,
                    body                TEXT,
                    lower_limit_text    TEXT,
                    upper_limit_text    TEXT,
                    is_closure          BOOLEAN DEFAULT 0,
                    is_drone_related    BOOLEAN DEFAULT 0,
                    is_restriction      BOOLEAN DEFAULT 0,
                    is_trigger_notam    BOOLEAN DEFAULT 0,
                    search_term         TEXT,
                    priority_score      INTEGER DEFAULT 0,
                    source              TEXT,
                    source_type         TEXT,
                    issue_date          DATETIME,
                    raw_icao_message    TEXT,
                    transaction_id      INTEGER,
                    has_history         BOOLEAN DEFAULT 0,
                    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Indexes for performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_notams_airport_code 
                ON notams(airport_code)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_notams_valid_dates 
                ON notams(valid_from, valid_to)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_notams_closure 
                ON notams(is_closure)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_notams_drone 
                ON notams(is_drone_related)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_notams_priority 
                ON notams(priority_score DESC)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_notams_search_term 
                ON notams(search_term)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_notams_type 
                ON notams(notam_type)
            ''')
            
            # search_runs table - lightweight audit log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_runs (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_term     TEXT,
                    airport_codes   TEXT,
                    mode            TEXT,
                    total_fetched   INTEGER,
                    new_inserted    INTEGER,
                    updated         INTEGER,
                    run_at          DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            logger.info(f"Database initialized at {self.db_path}")
    
    def upsert_notam(self, notam: Notam) -> Tuple[Optional[int], bool]:
        """
        Insert or update a NOTAM record.
        
        Args:
            notam: Notam instance
            
        Returns:
            Tuple of (row_id, was_inserted) where was_inserted is True for new records,
            False for updates
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if exists
            cursor.execute(
                'SELECT id, notam_type FROM notams WHERE notam_id = ?',
                (notam.notam_id,)
            )
            existing = cursor.fetchone()
            
            # Convert to dict for storage
            data = notam.to_dict()
            
            # Handle NOTAMC (cancel) specially
            if notam.notam_type == NotamType.CANCEL and existing:
                # This NOTAM cancels another - we'll update both
                if notam.cancels_notam_id:
                    cursor.execute('''
                        UPDATE notams 
                        SET notam_type = 'CANCEL',
                            updated_at = ?
                        WHERE notam_id = ?
                    ''', (datetime.now().isoformat(), notam.cancels_notam_id))
                    logger.info(f"Marked {notam.cancels_notam_id} as cancelled")
            
            if existing:
                # Update existing record
                cursor.execute('''
                    UPDATE notams SET
                        series = ?,
                        notam_type = ?,
                        replaces_notam_id = ?,
                        cancels_notam_id = ?,
                        fir = ?,
                        q_code = ?,
                        q_code_subject = ?,
                        q_code_condition = ?,
                        traffic = ?,
                        purpose = ?,
                        scope = ?,
                        lower_limit = ?,
                        upper_limit = ?,
                        coordinates = ?,
                        latitude = ?,
                        longitude = ?,
                        radius_nm = ?,
                        airport_code = ?,
                        airport_name = ?,
                        location = ?,
                        valid_from = ?,
                        valid_to = ?,
                        is_permanent = ?,
                        schedule = ?,
                        body = ?,
                        lower_limit_text = ?,
                        upper_limit_text = ?,
                        is_closure = ?,
                        is_drone_related = ?,
                        is_restriction = ?,
                        is_trigger_notam = ?,
                        search_term = ?,
                        priority_score = ?,
                        source = ?,
                        source_type = ?,
                        issue_date = ?,
                        raw_icao_message = ?,
                        transaction_id = ?,
                        has_history = ?,
                        updated_at = ?
                    WHERE notam_id = ?
                ''', (
                    data.get('series'),
                    data.get('notam_type'),
                    data.get('replaces_notam_id'),
                    data.get('cancels_notam_id'),
                    data.get('fir'),
                    data.get('q_code'),
                    data.get('q_code_subject'),
                    data.get('q_code_condition'),
                    data.get('traffic'),
                    data.get('purpose'),
                    data.get('scope'),
                    data.get('lower_limit'),
                    data.get('upper_limit'),
                    data.get('coordinates'),
                    data.get('latitude'),
                    data.get('longitude'),
                    data.get('radius_nm'),
                    data.get('airport_code'),
                    data.get('airport_name'),
                    data.get('location'),
                    data.get('valid_from'),
                    data.get('valid_to'),
                    1 if data.get('is_permanent') else 0,
                    data.get('schedule'),
                    data.get('body'),
                    data.get('lower_limit_text'),
                    data.get('upper_limit_text'),
                    1 if data.get('is_closure') else 0,
                    1 if data.get('is_drone_related') else 0,
                    1 if data.get('is_restriction') else 0,
                    1 if data.get('is_trigger_notam') else 0,
                    data.get('search_term'),
                    data.get('priority_score', 0),
                    data.get('source'),
                    data.get('source_type'),
                    data.get('issue_date'),
                    data.get('raw_icao_message'),
                    data.get('transaction_id'),
                    1 if data.get('has_history') else 0,
                    datetime.now().isoformat(),
                    notam.notam_id
                ))
                
                logger.debug(f"Updated NOTAM {notam.notam_id}")
                return existing['id'], False
            else:
                # Insert new record
                cursor.execute('''
                    INSERT INTO notams (
                        notam_id, series, notam_type, replaces_notam_id,
                        cancels_notam_id, fir, q_code, q_code_subject,
                        q_code_condition, traffic, purpose, scope,
                        lower_limit, upper_limit, coordinates, latitude,
                        longitude, radius_nm, airport_code, airport_name,
                        location, valid_from, valid_to, is_permanent,
                        schedule, body, lower_limit_text, upper_limit_text,
                        is_closure, is_drone_related, is_restriction,
                        is_trigger_notam, search_term, priority_score,
                        source, source_type, issue_date, raw_icao_message,
                        transaction_id, has_history, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    notam.notam_id,
                    data.get('series'),
                    data.get('notam_type'),
                    data.get('replaces_notam_id'),
                    data.get('cancels_notam_id'),
                    data.get('fir'),
                    data.get('q_code'),
                    data.get('q_code_subject'),
                    data.get('q_code_condition'),
                    data.get('traffic'),
                    data.get('purpose'),
                    data.get('scope'),
                    data.get('lower_limit'),
                    data.get('upper_limit'),
                    data.get('coordinates'),
                    data.get('latitude'),
                    data.get('longitude'),
                    data.get('radius_nm'),
                    data.get('airport_code'),
                    data.get('airport_name'),
                    data.get('location'),
                    data.get('valid_from'),
                    data.get('valid_to'),
                    1 if data.get('is_permanent') else 0,
                    data.get('schedule'),
                    data.get('body'),
                    data.get('lower_limit_text'),
                    data.get('upper_limit_text'),
                    1 if data.get('is_closure') else 0,
                    1 if data.get('is_drone_related') else 0,
                    1 if data.get('is_restriction') else 0,
                    1 if data.get('is_trigger_notam') else 0,
                    data.get('search_term'),
                    data.get('priority_score', 0),
                    data.get('source'),
                    data.get('source_type'),
                    data.get('issue_date'),
                    data.get('raw_icao_message'),
                    data.get('transaction_id'),
                    1 if data.get('has_history') else 0,
                    datetime.now().isoformat()
                ))
                
                logger.info(f"Inserted NOTAM {notam.notam_id} (score: {notam.priority_score})")
                return cursor.lastrowid, True
    
    def log_search_run(self, mode: str, search_term: Optional[str] = None,
                       airport_codes: Optional[List[str]] = None,
                       total_fetched: int = 0,
                       new_inserted: int = 0,
                       updated: int = 0) -> int:
        """
        Log a search run to the audit table.
        
        Args:
            mode: 'airport' or 'search'
            search_term: Search term used (for search mode)
            airport_codes: List of airport codes (for airport mode)
            total_fetched: Total records fetched
            new_inserted: New records inserted
            updated: Records updated
            
        Returns:
            ID of the log entry
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            airport_str = ','.join(airport_codes) if airport_codes else None
            
            cursor.execute('''
                INSERT INTO search_runs
                (search_term, airport_codes, mode, total_fetched, new_inserted, updated)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                search_term,
                airport_str,
                mode,
                total_fetched,
                new_inserted,
                updated
            ))
            
            return cursor.lastrowid
    
    def get_active_notams(self, min_score: int = 0) -> List[Dict]:
        """
        Get currently active NOTAMs.
        
        Args:
            min_score: Minimum priority score filter
            
        Returns:
            List of NOTAM dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Active = valid_to is NULL (permanent) OR valid_to > now
            # AND not cancelled/expired (notam_type != 'CANCEL')
            cursor.execute('''
                SELECT * FROM notams
                WHERE (valid_to IS NULL OR valid_to > datetime('now'))
                  AND (notam_type != 'CANCEL' OR notam_type IS NULL)
                  AND priority_score >= ?
                ORDER BY priority_score DESC, valid_from DESC
            ''', (min_score,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_closures(self, active_only: bool = True) -> List[Dict]:
        """
        Get closure NOTAMs.
        
        Args:
            active_only: If True, only return active closures
            
        Returns:
            List of NOTAM dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT * FROM notams
                WHERE is_closure = 1
            '''
            
            if active_only:
                query += ''' AND (valid_to IS NULL OR valid_to > datetime('now'))
                              AND (notam_type != 'CANCEL' OR notam_type IS NULL)'''
            
            query += ' ORDER BY priority_score DESC, valid_from DESC'
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_drone_notams(self, active_only: bool = True) -> List[Dict]:
        """
        Get drone-related NOTAMs.
        
        Args:
            active_only: If True, only return active NOTAMs
            
        Returns:
            List of NOTAM dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT * FROM notams
                WHERE is_drone_related = 1
            '''
            
            if active_only:
                query += ''' AND (valid_to IS NULL OR valid_to > datetime('now'))
                              AND (notam_type != 'CANCEL' OR notam_type IS NULL)'''
            
            query += ' ORDER BY priority_score DESC, valid_from DESC'
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_by_search_term(self, term: str, active_only: bool = True) -> List[Dict]:
        """
        Get NOTAMs by search term.
        
        Args:
            term: Search term
            active_only: If True, only return active NOTAMs
            
        Returns:
            List of NOTAM dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT * FROM notams
                WHERE search_term = ?
            '''
            
            if active_only:
                query += ''' AND (valid_to IS NULL OR valid_to > datetime('now'))
                              AND (notam_type != 'CANCEL' OR notam_type IS NULL)'''
            
            query += ' ORDER BY priority_score DESC, valid_from DESC'
            
            cursor.execute(query, (term,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_by_airport(self, airport_code: str, active_only: bool = True) -> List[Dict]:
        """
        Get NOTAMs by airport code.
        
        Args:
            airport_code: ICAO airport code
            active_only: If True, only return active NOTAMs
            
        Returns:
            List of NOTAM dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT * FROM notams
                WHERE airport_code = ?
            '''
            
            if active_only:
                query += ''' AND (valid_to IS NULL OR valid_to > datetime('now'))
                              AND (notam_type != 'CANCEL' OR notam_type IS NULL)'''
            
            query += ' ORDER BY priority_score DESC, valid_from DESC'
            
            cursor.execute(query, (airport_code,))
            return [dict(row) for row in cursor.fetchall()]
    
    def purge_expired(self, days_after_expiry: int = 30) -> int:
        """
        Delete NOTAMs that expired more than N days ago.
        
        Args:
            days_after_expiry: Delete if valid_to < now - days_after_expiry
            
        Returns:
            Number of records deleted
        """
        cutoff = (datetime.now() - timedelta(days=days_after_expiry)).isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM notams
                WHERE valid_to IS NOT NULL
                  AND valid_to < ?
            ''', (cutoff,))
            
            count = cursor.rowcount
            logger.info(f"Purged {count} expired NOTAMs (older than {cutoff})")
            return count
    
    def purge_cancelled(self, days_after_cancel: int = 7) -> int:
        """
        Delete cancelled NOTAMs older than N days.
        
        Args:
            days_after_cancel: Delete if cancelled and older than this
            
        Returns:
            Number of records deleted
        """
        cutoff = (datetime.now() - timedelta(days=days_after_cancel)).isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM notams
                WHERE notam_type = 'CANCEL'
                  AND updated_at < ?
            ''', (cutoff,))
            
            count = cursor.rowcount
            logger.info(f"Purged {count} cancelled NOTAMs (older than {cutoff})")
            return count
    
    def purge_old_search_runs(self, keep_days: int = 90) -> int:
        """
        Trim the search_runs audit log.
        
        Args:
            keep_days: Keep records from the last N days
            
        Returns:
            Number of records deleted
        """
        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM search_runs
                WHERE run_at < ?
            ''', (cutoff,))
            
            count = cursor.rowcount
            logger.info(f"Purged {count} old search run records")
            return count
    
    def execute_custom_query(self, query: str) -> List[Dict]:
        """Execute a custom SQL query."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_statistics(self) -> Dict:
        """Get summary statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Total NOTAMs
            cursor.execute('SELECT COUNT(*) as total FROM notams')
            stats['total_notams'] = cursor.fetchone()['total']
            
            # Active NOTAMs
            cursor.execute('''
                SELECT COUNT(*) as active FROM notams
                WHERE (valid_to IS NULL OR valid_to > datetime('now'))
                  AND (notam_type != 'CANCEL' OR notam_type IS NULL)
            ''')
            stats['active_notams'] = cursor.fetchone()['active']
            
            # Closures
            cursor.execute('SELECT COUNT(*) as closures FROM notams WHERE is_closure = 1')
            stats['closures'] = cursor.fetchone()['closures']
            
            # Active closures
            cursor.execute('''
                SELECT COUNT(*) as active_closures FROM notams
                WHERE is_closure = 1
                  AND (valid_to IS NULL OR valid_to > datetime('now'))
                  AND (notam_type != 'CANCEL' OR notam_type IS NULL)
            ''')
            stats['active_closures'] = cursor.fetchone()['active_closures']
            
            # Drone-related
            cursor.execute('SELECT COUNT(*) as drone FROM notams WHERE is_drone_related = 1')
            stats['drone_notams'] = cursor.fetchone()['drone']
            
            # Active drone
            cursor.execute('''
                SELECT COUNT(*) as active_drone FROM notams
                WHERE is_drone_related = 1
                  AND (valid_to IS NULL OR valid_to > datetime('now'))
                  AND (notam_type != 'CANCEL' OR notam_type IS NULL)
            ''')
            stats['active_drone_notams'] = cursor.fetchone()['active_drone']
            
            # High priority (score >= 80)
            cursor.execute('''
                SELECT COUNT(*) as high_priority FROM notams
                WHERE priority_score >= 80
            ''')
            stats['high_priority'] = cursor.fetchone()['high_priority']
            
            return stats