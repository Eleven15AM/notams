"""Database module for storing NOTAM data."""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager
import logging

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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS airport_closures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notam_id TEXT NOT NULL UNIQUE,
                    airport_code TEXT NOT NULL,
                    airport_name TEXT,
                    issue_date DATETIME NOT NULL,
                    closure_start DATETIME NOT NULL,
                    closure_end DATETIME,
                    reason TEXT NOT NULL,
                    full_text TEXT,
                    weight INTEGER DEFAULT 1,
                    is_drone_related BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_airport_code 
                ON airport_closures(airport_code)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_closure_dates 
                ON airport_closures(closure_start, closure_end)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_drone_related 
                ON airport_closures(is_drone_related)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_issue_date 
                ON airport_closures(issue_date)
            ''')
            
            logger.info(f"Database initialized at {self.db_path}")
    
    def insert_closure(self, closure_data: Dict) -> Optional[int]:
        """
        Insert a new airport closure record.
        Uses INSERT OR IGNORE to prevent duplicates.
        
        Returns:
            Row ID if inserted, None if duplicate
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if already exists
            cursor.execute(
                'SELECT id FROM airport_closures WHERE notam_id = ?',
                (closure_data['notam_id'],)
            )
            existing = cursor.fetchone()
            
            if existing:
                logger.debug(f"NOTAM {closure_data['notam_id']} already exists, skipping")
                return None
            
            cursor.execute('''
                INSERT INTO airport_closures 
                (notam_id, airport_code, airport_name, issue_date, closure_start, closure_end, 
                 reason, full_text, weight, is_drone_related, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                closure_data['notam_id'],
                closure_data['airport_code'],
                closure_data.get('airport_name'),
                closure_data['issue_date'],
                closure_data['closure_start'],
                closure_data.get('closure_end'),
                closure_data['reason'],
                closure_data.get('full_text'),
                closure_data['weight'],
                closure_data['is_drone_related'],
                datetime.now().isoformat()
            ))
            
            return cursor.lastrowid
    
    def get_active_closures(self) -> List[Dict]:
        """Get all currently active closures."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM airport_closures
                WHERE closure_end IS NULL 
                   OR closure_end > datetime('now')
                ORDER BY weight DESC, closure_start DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_todays_closures(self) -> List[Dict]:
        """Get closures for today (started today or active today)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM airport_closures
                WHERE (
                    date(closure_start) = date('now')
                    OR (
                        closure_start <= datetime('now')
                        AND (closure_end IS NULL OR closure_end >= datetime('now'))
                    )
                )
                ORDER BY weight DESC, closure_start DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_closures_by_airport(self, airport_code: str) -> List[Dict]:
        """Get all closures for a specific airport."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM airport_closures
                WHERE airport_code = ?
                ORDER BY closure_start DESC
            ''', (airport_code,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_drone_closures(self) -> List[Dict]:
        """Get all drone-related closures."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM airport_closures
                WHERE is_drone_related = 1
                ORDER BY closure_start DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
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
            
            # Total closures
            cursor.execute('SELECT COUNT(*) as total FROM airport_closures')
            stats['total_closures'] = cursor.fetchone()['total']
            
            # Active closures
            cursor.execute('''
                SELECT COUNT(*) as active FROM airport_closures
                WHERE closure_end IS NULL OR closure_end > datetime('now')
            ''')
            stats['active_closures'] = cursor.fetchone()['active']
            
            # Today's closures
            cursor.execute('''
                SELECT COUNT(*) as today FROM airport_closures
                WHERE date(closure_start) = date('now')
                   OR (
                       closure_start <= datetime('now')
                       AND (closure_end IS NULL OR closure_end >= datetime('now'))
                   )
            ''')
            stats['todays_closures'] = cursor.fetchone()['today']
            
            # Drone-related closures
            cursor.execute('''
                SELECT COUNT(*) as drone FROM airport_closures
                WHERE is_drone_related = 1
            ''')
            stats['drone_closures'] = cursor.fetchone()['drone']
            
            # Active drone closures
            cursor.execute('''
                SELECT COUNT(*) as active_drone FROM airport_closures
                WHERE is_drone_related = 1
                  AND (closure_end IS NULL OR closure_end > datetime('now'))
            ''')
            stats['active_drone_closures'] = cursor.fetchone()['active_drone']
            
            return stats