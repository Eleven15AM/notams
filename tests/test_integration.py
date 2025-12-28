"""Integration tests for the complete NOTAM system."""
import pytest
import tempfile
import os
from src.database import NotamDatabase
from src.parser import NotamParser
from src.notam_client import FAANotamClient
from src.config import Config


class TestIntegration:
    """Integration tests for complete workflows."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        try:
            os.unlink(path)
        except:
            pass
    
    @pytest.fixture
    def db(self, temp_db_path):
        """Create database instance."""
        return NotamDatabase(temp_db_path)
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return NotamParser()
    
    @pytest.fixture
    def sample_faa_notams(self):
        """Sample NOTAMs in FAA API format with current/future dates."""
        from datetime import datetime, timedelta
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        next_week = now + timedelta(days=7)
        
        return [
            {
                'facilityDesignator': 'EKCH',
                'notamNumber': 'A3097/25',
                'airportName': 'KASTRUP',
                'issueDate': now.strftime('%m/%d/%Y %H%M'),
                'startDate': now.strftime('%m/%d/%Y %H%M'),
                'endDate': tomorrow.strftime('%m/%d/%Y %H%M'),
                'status': 'Active',
                'cancelledOrExpired': False,
                'icaoMessage': 'RWY 12/30 CLSD FOR TKOF AND LDG DUE TO WIP.'
            },
            {
                'facilityDesignator': 'EGLL',
                'notamNumber': 'A0001/25',
                'airportName': 'HEATHROW',
                'issueDate': now.strftime('%m/%d/%Y %H%M'),
                'startDate': now.strftime('%m/%d/%Y %H%M'),
                'endDate': next_week.strftime('%m/%d/%Y %H%M'),
                'status': 'Active',
                'cancelledOrExpired': False,
                'icaoMessage': 'AIRPORT CLOSED DUE TO UNAUTHORIZED DRONE ACTIVITY'
            },
            {
                'facilityDesignator': 'LFPG',
                'notamNumber': 'A0002/25',
                'airportName': 'CHARLES DE GAULLE',
                'issueDate': now.strftime('%m/%d/%Y %H%M'),
                'startDate': now.strftime('%m/%d/%Y %H%M'),
                'endDate': 'PERM',
                'status': 'Active',
                'cancelledOrExpired': False,
                'icaoMessage': 'TAXIWAY ALPHA LIGHTING UNSERVICEABLE'
            }
        ]
    
    def test_parse_and_store_workflow(self, db, parser, sample_faa_notams):
        """Test complete workflow: parse NOTAMs and store in database."""
        closure_count = 0
        
        for notam in sample_faa_notams:
            closure_data = parser.parse_notam(notam)
            
            if closure_data:
                closure_count += 1
                row_id = db.insert_closure(closure_data)
                assert row_id is not None
        
        # Should have parsed 2 closures (RWY closed and AIRPORT closed)
        # Taxiway lighting is not a closure
        assert closure_count == 2
        
        # Verify data in database
        all_closures = db.get_active_closures()
        assert len(all_closures) == 2
    
    def test_drone_detection_workflow(self, db, parser, sample_faa_notams):
        """Test that drone closures are detected and weighted."""
        for notam in sample_faa_notams:
            closure_data = parser.parse_notam(notam)
            if closure_data:
                db.insert_closure(closure_data)
        
        drone_closures = db.get_drone_closures()
        
        # Should have one drone closure
        assert len(drone_closures) == 1
        assert drone_closures[0]['weight'] == 10
        assert drone_closures[0]['is_drone_related'] == 1
    
    def test_weight_prioritization(self, db, parser, sample_faa_notams):
        """Test that high-weight closures appear first."""
        for notam in sample_faa_notams:
            closure_data = parser.parse_notam(notam)
            if closure_data:
                db.insert_closure(closure_data)
        
        active = db.get_active_closures()
        
        # Drone closure should be first (weight 10)
        assert active[0]['is_drone_related'] == 1
        assert active[0]['weight'] == 10
    
    def test_statistics_accuracy(self, db, parser, sample_faa_notams):
        """Test that statistics are accurate."""
        for notam in sample_faa_notams:
            closure_data = parser.parse_notam(notam)
            if closure_data:
                db.insert_closure(closure_data)
        
        stats = db.get_statistics()
        
        assert stats['total_closures'] == 2
        assert stats['drone_closures'] == 1
        assert stats['active_closures'] >= 1
    
    def test_duplicate_handling(self, db, parser, sample_faa_notams):
        """Test that duplicate NOTAMs are handled correctly."""
        # Process NOTAMs twice
        for _ in range(2):
            for notam in sample_faa_notams:
                closure_data = parser.parse_notam(notam)
                if closure_data:
                    db.insert_closure(closure_data)
        
        # Should still only have 2 records
        stats = db.get_statistics()
        assert stats['total_closures'] == 2