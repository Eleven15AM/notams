"""Unit tests for database operations."""
import pytest
import tempfile
import os
from datetime import datetime, timedelta
from src.database import NotamDatabase


class TestNotamDatabase:
    """Test cases for NotamDatabase class."""
    
    @pytest.fixture
    def db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        database = NotamDatabase(path)
        
        yield database
        
        # Cleanup
        try:
            os.unlink(path)
        except:
            pass
    
    @pytest.fixture
    def sample_closure(self):
        """Create sample closure data in FAA format."""
        now = datetime.now()
        return {
            'notam_id': 'A3097/25',
            'airport_code': 'EKCH',
            'airport_name': 'KASTRUP',
            'issue_date': now.isoformat(),
            'closure_start': now.isoformat(),
            'closure_end': (now + timedelta(hours=6)).isoformat(),
            'reason': 'RWY 12/30 CLSD FOR TKOF AND LDG DUE TO WIP',
            'full_text': 'Full ICAO message text here',
            'weight': 1,
            'is_drone_related': False
        }
    
    @pytest.fixture
    def sample_drone_closure(self):
        """Create sample drone closure data."""
        now = datetime.now()
        return {
            'notam_id': 'A0001/25',
            'airport_code': 'EGLL',
            'airport_name': 'HEATHROW',
            'issue_date': now.isoformat(),
            'closure_start': now.isoformat(),
            'closure_end': (now + timedelta(hours=3)).isoformat(),
            'reason': 'AIRPORT CLOSED DUE TO DRONE ACTIVITY',
            'full_text': 'Full message about drone',
            'weight': 10,
            'is_drone_related': True
        }
    
    def test_database_initialization(self, db):
        """Test that database tables are created."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='airport_closures'
            """)
            result = cursor.fetchone()
            
            assert result is not None
            assert result['name'] == 'airport_closures'
    
    def test_insert_closure(self, db, sample_closure):
        """Test inserting a closure record."""
        record_id = db.insert_closure(sample_closure)
        
        assert record_id is not None
        assert record_id > 0
        
        # Verify record was inserted
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM airport_closures WHERE id = ?', (record_id,))
            result = cursor.fetchone()
            
            assert result is not None
            assert result['notam_id'] == 'A3097/25'
            assert result['airport_code'] == 'EKCH'
            assert result['airport_name'] == 'KASTRUP'
    
    def test_insert_duplicate_notam_id(self, db, sample_closure):
        """Test that duplicate NOTAM IDs are ignored."""
        # Insert first time
        first_id = db.insert_closure(sample_closure)
        assert first_id is not None
        
        # Try to insert again - should return None (duplicate)
        second_id = db.insert_closure(sample_closure)
        assert second_id is None
        
        # Check that only one record exists
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) as count FROM airport_closures WHERE notam_id = ?',
                (sample_closure['notam_id'],)
            )
            result = cursor.fetchone()
            
            assert result['count'] == 1
    
    def test_get_active_closures(self, db, sample_closure):
        """Test retrieving active closures."""
        db.insert_closure(sample_closure)
        
        active = db.get_active_closures()
        
        assert len(active) >= 1
        assert any(c['notam_id'] == 'A3097/25' for c in active)
    
    def test_get_todays_closures(self, db, sample_closure):
        """Test retrieving today's closures."""
        db.insert_closure(sample_closure)
        
        todays = db.get_todays_closures()
        
        assert len(todays) >= 1
        assert any(c['notam_id'] == 'A3097/25' for c in todays)
    
    def test_get_drone_closures(self, db, sample_closure, sample_drone_closure):
        """Test retrieving only drone-related closures."""
        db.insert_closure(sample_closure)
        db.insert_closure(sample_drone_closure)
        
        drone_closures = db.get_drone_closures()
        
        assert len(drone_closures) >= 1
        assert all(c['is_drone_related'] == 1 for c in drone_closures)
        assert any(c['notam_id'] == 'A0001/25' for c in drone_closures)
    
    def test_weight_ordering(self, db, sample_closure, sample_drone_closure):
        """Test that drone closures (higher weight) appear first."""
        db.insert_closure(sample_closure)
        db.insert_closure(sample_drone_closure)
        
        active = db.get_active_closures()
        
        # First result should be drone closure (weight 10)
        assert active[0]['weight'] == 10
        assert active[0]['is_drone_related'] == 1
    
    def test_statistics(self, db, sample_closure, sample_drone_closure):
        """Test statistics retrieval."""
        db.insert_closure(sample_closure)
        db.insert_closure(sample_drone_closure)
        
        stats = db.get_statistics()
        
        assert stats['total_closures'] >= 2
        assert stats['active_closures'] >= 2
        assert stats['todays_closures'] >= 0
        assert stats['drone_closures'] >= 1
        assert stats['active_drone_closures'] >= 1