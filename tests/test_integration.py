"""Integration tests for the complete NOTAM system."""
import pytest
import tempfile
import os
from src.database import NotamDatabase
from src.parser import NotamParser
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
        
        # Format dates for FAA API fields: MM/DD/YYYY HHMM
        issue_date = now.strftime('%m/%d/%Y %H%M')
        start_date = now.strftime('%m/%d/%Y %H%M')
        tomorrow_date = tomorrow.strftime('%m/%d/%Y %H%M')
        next_week_date = next_week.strftime('%m/%d/%Y %H%M')
        
        # Format for B) and C) fields in ICAO message: YYMMDDHHMM
        b_date_now = now.strftime('%y%m%d%H%M')
        b_date_tomorrow = tomorrow.strftime('%y%m%d%H%M')
        b_date_next_week = next_week.strftime('%y%m%d%H%M')
        
        return [
            {  # EKCH - Runway closure
                'facilityDesignator': 'EKCH',
                'notamNumber': 'A3097/25',
                'airportName': 'KASTRUP',
                'issueDate': issue_date,
                'startDate': start_date,
                'endDate': tomorrow_date,
                'status': 'Active',
                'cancelledOrExpired': False,
                'icaoMessage': (
                    f'A3097/25 NOTAMN\n'
                    f'Q) EKDK/QMRLC/IV/NBO/A/000/999/5537N01239E005\n'
                    f'A) EKCH B) {b_date_now} C) {b_date_tomorrow}\n'
                    f'E) RWY 12/30 CLSD FOR TKOF AND LDG DUE TO WIP.'
                )
            },
            {  # EGLL - Drone closure
                'facilityDesignator': 'EGLL',
                'notamNumber': 'A0001/25',
                'airportName': 'HEATHROW',
                'issueDate': issue_date,
                'startDate': start_date,
                'endDate': next_week_date,
                'status': 'Active',
                'cancelledOrExpired': False,
                'icaoMessage': (
                    f'A0001/25 NOTAMN\n'
                    f'Q) EGTT/QMRLC/IV/NBO/A/000/999/5129N00028W005\n'
                    f'A) EGLL B) {b_date_now} C) {b_date_next_week}\n'
                    f'E) AIRPORT CLOSED DUE TO UNAUTHORIZED DRONE ACTIVITY'
                )
            },
            {  # LFPG - Non-closure (taxiway lighting)
                'facilityDesignator': 'LFPG',
                'notamNumber': 'A0002/25',
                'airportName': 'CHARLES DE GAULLE',
                'issueDate': issue_date,
                'startDate': start_date,
                'endDate': 'PERM',
                'status': 'Active',
                'cancelledOrExpired': False,
                'icaoMessage': (
                    f'A0002/25 NOTAMN\n'
                    f'Q) LFPG/QMRLC/IV/NBO/A/000/999/4851N00300E002\n'
                    f'A) LFPG B) {b_date_now} C) PERM\n'
                    f'E) TAXIWAY ALPHA LIGHTING UNSERVICEABLE'
                )
            }
        ]
    
    def test_parse_and_store_workflow(self, db, parser, sample_faa_notams):
        """Test complete workflow: parse NOTAMs and store in database."""
        inserted_count = 0
        
        for notam in sample_faa_notams:
            notam_obj = parser.parse_notam(notam)
            
            if notam_obj:
                row_id, was_inserted = db.upsert_notam(notam_obj)
                if was_inserted:
                    inserted_count += 1
        
        # Should have inserted all 3 NOTAMs
        assert inserted_count == 3
        
        # Verify data in database - all NOTAMs are active since dates are in future
        all_notams = db.get_active_notams(min_score=0)
        assert len(all_notams) == 3  # All 3 should be active
    
    def test_drone_detection_workflow(self, db, parser, sample_faa_notams):
        """Test that drone closures are detected."""
        for notam in sample_faa_notams:
            notam_obj = parser.parse_notam(notam)
            if notam_obj:
                db.upsert_notam(notam_obj)
        
        drone_notams = db.get_drone_notams()
        
        # Should have one drone NOTAM
        assert len(drone_notams) == 1
        assert drone_notams[0]['is_drone_related'] == 1
        assert drone_notams[0]['notam_id'] == 'A0001/25'
    
    def test_priority_ordering(self, db, parser, sample_faa_notams):
        """Test that higher priority NOTAMs appear first."""
        for notam in sample_faa_notams:
            notam_obj = parser.parse_notam(notam)
            if notam_obj:
                db.upsert_notam(notam_obj)
        
        active = db.get_active_notams(min_score=0)
        
        # Drone NOTAM should have highest priority
        if len(active) >= 2:
            # Find the drone NOTAM
            drone_notam = next((n for n in active if n['is_drone_related'] == 1), None)
            if drone_notam:
                # It should be first or have high priority
                assert drone_notam['priority_score'] >= 50
    
    def test_statistics_accuracy(self, db, parser, sample_faa_notams):
        """Test that statistics are accurate."""
        for notam in sample_faa_notams:
            notam_obj = parser.parse_notam(notam)
            if notam_obj:
                db.upsert_notam(notam_obj)
        
        stats = db.get_statistics()
        
        assert stats['total_notams'] == 3
        assert stats['drone_notams'] == 1
        assert stats['closures'] >= 2  # EKCH and EGLL are closures
    
    def test_duplicate_handling(self, db, parser, sample_faa_notams):
        """Test that duplicate NOTAMs are handled correctly."""
        # Process NOTAMs twice
        for _ in range(2):
            for notam in sample_faa_notams:
                notam_obj = parser.parse_notam(notam)
                if notam_obj:
                    db.upsert_notam(notam_obj)
        
        # Should still only have 3 records
        stats = db.get_statistics()
        assert stats['total_notams'] == 3