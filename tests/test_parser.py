"""Unit tests for NOTAM parser."""
import pytest
from datetime import datetime
from src.parser import NotamParser


class TestNotamParser:
    """Test cases for NotamParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return NotamParser()
    
    @pytest.fixture
    def sample_faa_notam(self):
        """Sample NOTAM in FAA API format with current dates."""
        from datetime import datetime, timedelta
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        
        return {
            'facilityDesignator': 'EKCH',
            'notamNumber': 'A3097/25',
            'airportName': 'KASTRUP',
            'issueDate': now.strftime('%m/%d/%Y %H%M'),
            'startDate': now.strftime('%m/%d/%Y %H%M'),
            'endDate': tomorrow.strftime('%m/%d/%Y %H%M'),
            'status': 'Active',
            'cancelledOrExpired': False,
            'icaoMessage': 'A3097/25 NOTAMN\nQ) EKDK/QMRLC/IV/NBO/A/000/999/5537N01239E005\nA) EKCH B) 2512072100 C) 2512080500\nE) RWY 12/30 CLSD FOR TKOF AND LDG DUE TO WIP.'
        }
    
    def test_parse_closure_notam(self, parser, sample_faa_notam):
        """Test parsing a basic closure NOTAM."""
        result = parser.parse_notam(sample_faa_notam)
        
        assert result is not None
        assert result.notam_id == 'A3097/25'
        assert result.airport_code == 'EKCH'
        assert result.airport_name == 'KASTRUP'
        assert result.is_drone_related is False
        assert result.is_closure is True
        assert result.valid_from is not None
        assert result.valid_to is not None
    
    def test_parse_drone_closure(self, parser):
        """Test parsing a drone-related closure."""
        from datetime import datetime, timedelta
        now = datetime.now()
        future = now + timedelta(hours=6)
        
        notam_data = {
            'facilityDesignator': 'EGLL',
            'notamNumber': 'A0001/25',
            'airportName': 'HEATHROW',
            'issueDate': now.strftime('%m/%d/%Y %H%M'),
            'startDate': now.strftime('%m/%d/%Y %H%M'),
            'endDate': future.strftime('%m/%d/%Y %H%M'),
            'status': 'Active',
            'cancelledOrExpired': False,
            'icaoMessage': 'A0001/25 NOTAMN\nE) AIRPORT CLOSED DUE TO UNAUTHORIZED DRONE ACTIVITY IN VICINITY'
        }
        
        result = parser.parse_notam(notam_data)
        
        assert result is not None
        assert result.is_drone_related is True
        assert result.is_closure is True
    
    def test_parse_uas_closure(self, parser):
        """Test parsing UAS (unmanned aircraft) closure."""
        from datetime import datetime
        now = datetime.now()
        
        # Format for B) field: YYMMDDHHMM
        b_date = now.strftime('%y%m%d%H%M')

        notam_data = {
            'facilityDesignator': 'LFPG',
            'notamNumber': 'A0002/25',
            'airportName': 'CHARLES DE GAULLE',
            'issueDate': now.strftime('%m/%d/%Y %H%M'),
            'startDate': now.strftime('%m/%d/%Y %H%M'),
            'endDate': 'PERM',
            'status': 'Active',
            'cancelledOrExpired': False,
            'icaoMessage': (
                f'A0002/25 NOTAMN\n'
                f'Q) LFPG/QRLC/IV/NBO/A/000/999/4851N00300E002\n'
                f'A) LFPG B) {b_date} C) PERM\n'
                f'E) RUNWAY CLSD DUE TO UAS SIGHTING'
            )
        }

        result = parser.parse_notam(notam_data)

        assert result is not None
        assert result.is_drone_related is True
        assert result.is_permanent is True

    def test_parse_rov_closure(self, parser):
        """Test parsing rov wording (e.g. APPROVED) in closure."""
        from datetime import datetime
        now = datetime.now()
        
        notam_data = {
            'facilityDesignator': 'LFPG',
            'notamNumber': 'A0022/25',
            'airportName': 'CHARLES DE GAULLE',
            'issueDate': now.strftime('%m/%d/%Y %H%M'),
            'startDate': now.strftime('%m/%d/%Y %H%M'),
            'endDate': 'PERM',
            'status': 'Active',
            'cancelledOrExpired': False,
            'icaoMessage': 'A0022/25 NOTAMN\nE) AD CLSD. FLT DURING CLOSURE PERIOD MUST BE PRIOR APPROVED ACFT'
        }
        
        result = parser.parse_notam(notam_data)
        
        assert result is not None
        assert result.is_drone_related is False
        assert result.is_closure is True

    def test_skip_cancelled_notam(self, parser, sample_faa_notam):
        """Test that cancelled NOTAMs are skipped."""
        sample_faa_notam['cancelledOrExpired'] = True
        
        result = parser.parse_notam(sample_faa_notam)
        
        assert result is None
    
    def test_skip_expired_notam(self, parser, sample_faa_notam):
        """Test that expired NOTAMs are skipped."""
        sample_faa_notam['status'] = 'Expired'
        
        result = parser.parse_notam(sample_faa_notam)
        
        assert result is None
    
    def test_parse_non_closure_notam(self, parser):
        """Test that non-closure NOTAMs are still parsed (they're valuable for search mode)."""
        from datetime import datetime
        now = datetime.now()
        
        notam_data = {
            'facilityDesignator': 'EDDF',
            'notamNumber': 'A0003/25',
            'airportName': 'FRANKFURT',
            'issueDate': now.strftime('%m/%d/%Y %H%M'),
            'startDate': now.strftime('%m/%d/%Y %H%M'),
            'endDate': now.strftime('%m/%d/%Y %H%M'),
            'status': 'Active',
            'cancelledOrExpired': False,
            'icaoMessage': 'A0003/25 NOTAMN\nE) TAXIWAY LIGHTING UNSERVICEABLE'
        }
        
        result = parser.parse_notam(notam_data)
        
        # Should return a Notam object even if not a closure
        assert result is not None
        assert result.notam_id == 'A0003/25'
        assert result.is_closure is False
    
    def test_is_closure_notam_variants(self, parser):
        """Test different closure keyword variants."""
        test_cases = [
            ('AERODROME CLOSED', True),
            ('AD CLSD', True),
            ('AIRPORT CLOSURE IN EFFECT', True),
            ('NOT AVBL', True),
            ('RUNWAY 27L UNAVAILABLE', True),
            ('RWY 12/30 CLSD FOR TKOF', True),
            ('LIGHTING UNSERVICEABLE', False),
            ('FREQUENCY CHANGE', False)
        ]
        
        for text, expected in test_cases:
            result = parser._is_closure_notam(text)
            assert result == expected, f"Failed for text: {text}"
    
    def test_is_drone_related_variants(self, parser):
        """Test different drone keyword variants."""
        test_cases = [
            ('DRONE ACTIVITY REPORTED', True),
            ('UAS SIGHTING IN VICINITY', True),
            ('UNMANNED AIRCRAFT DETECTED', True),
            ('RPAS OPERATION', True),
            ('UAV DETECTED', True),
            ('MAINTENANCE WORK', False),
            ('WEATHER CONDITIONS', False)
        ]
        
        for text, expected in test_cases:
            result = parser._is_drone_related(text)
            assert result == expected, f"Failed for text: {text}"
    
    def test_parse_faa_date_format(self, parser):
        """Test FAA date format parsing."""
        from datetime import datetime
        
        # Create a fixed test date
        test_date = "01/15/2025 1430"
        
        test_cases = [
            (test_date, "2025-01-15T14:30:00"),  # Should parse to ISO format
            ('PERM', None),
            ('', None),
            (None, None)
        ]
        
        for date_str, expected in test_cases:
            result = parser._parse_date(date_str)
            if expected:
                assert result is not None
                # Convert datetime to string for comparison
                assert result.isoformat().startswith(expected[:10])
            else:
                assert result is None