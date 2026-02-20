"""Unit tests for Notam domain model."""
import pytest
from datetime import datetime
from src.models.notam import Notam, NotamType


class TestNotamModel:
    """Test cases for Notam class."""
    
    @pytest.fixture
    def sample_notamn(self):
        """Sample NOTAMN from FAA API."""
        return {
            "facilityDesignator": "LFJL",
            "notamNumber": "R3281/24",
            "issueDate": "11/14/2024 0847",
            "startDate": "11/28/2024 0000",
            "endDate": "04/15/2026 2359",
            "source": "USNS",
            "sourceType": "I",
            "icaoMessage": (
                "R3281/24 NOTAMN\n"
                "Q) LFEE/QRTTT/IV/BO /AW/000/014/4904N00607E003\n"
                "A) LFJL B) 2411280000 C) 2604152359\n"
                "E) TRIGGER NOTAM - AIP SUP 216/24.\n"
                "DRONE ACTIVITY OVER 'METZ-FRESCATY' REQUIRING THE CREATION OF 2 \n"
                "TEMPORARY RESTRICTED AREAS.\n"
                "F) SFC G) 1400FT AMSL"
            ),
            "icaoId": "LFJL",
            "airportName": "METZ NANCY LORRAINE",
            "cancelledOrExpired": False,
            "status": "Active",
            "transactionID": 74271625,
            "hasHistory": True
        }
    
    @pytest.fixture
    def sample_notamr(self):
        """Sample NOTAMR from FAA API."""
        return {
            "facilityDesignator": "LFPK",
            "notamNumber": "R2198/25",
            "issueDate": "09/12/2025 1430",
            "startDate": "09/12/2025 1429",
            "endDate": "11/25/2026 1930",
            "source": "USNS",
            "sourceType": "I",
            "icaoMessage": (
                "R2198/25 NOTAMR R1978/25\n"
                "Q) LFFF/QRTTT/IV/BO /AW/000/017/4851N00300E002\n"
                "A) LFPK B) 2509121429 C) 2611251930\n"
                "E) TRIGGER NOTAM - AIP SUP 147/25 : \n"
                "DRONE FLIGHTS AND PYROTECHNIC ACTIVITIES REQUIRING THE CREATION OF 2 \n"
                "TEMPORARY RESTRICTED AREAS AND AD USE RESTRICTIONS.\n"
                "F) SFC G) 1700FT AMSL"
            ),
            "icaoId": "LFPK",
            "airportName": "COULOMMIERS VOISINS",
            "cancelledOrExpired": False,
            "status": "Active",
            "transactionID": 77919705,
            "hasHistory": False
        }
    
    def test_from_api_dict_new_notam(self, sample_notamn):
        """Test parsing a NOTAMN."""
        notam = Notam.from_api_dict(sample_notamn)
        
        assert notam.notam_id == "R3281/24"
        assert notam.series == "R"
        assert notam.number == 3281
        # Year from NOTAM ID is 24 (2-digit), not the full year from dates
        assert notam.year == 24
        assert notam.notam_type == NotamType.NEW
        assert notam.replaces_notam_id is None
        assert notam.cancels_notam_id is None
        
        # Q-Line
        assert notam.fir == "LFEE"
        assert notam.q_code == "QRTTT"
        assert notam.traffic == "IV"
        assert notam.purpose == "BO"
        assert notam.scope == "AW"
        assert notam.lower_limit == 0
        assert notam.upper_limit == 14
        assert notam.coordinates == "4904N00607E003"
        assert notam.latitude == pytest.approx(49.0667, 0.01)
        assert notam.longitude == pytest.approx(6.1167, 0.01)
        assert notam.radius_nm == 3
        
        # Lettered fields
        assert notam.location == "LFJL"
        assert notam.valid_from is not None
        assert notam.valid_to is not None
        assert not notam.is_permanent
        assert notam.schedule is None
        assert "DRONE ACTIVITY" in notam.body
        assert notam.lower_limit_text == "SFC"
        assert notam.upper_limit_text == "1400FT AMSL"
        
        # Source metadata
        assert notam.airport_code == "LFJL"
        assert notam.airport_name == "METZ NANCY LORRAINE"
        assert notam.source == "USNS"
        assert notam.transaction_id == 74271625
        assert notam.has_history is True
        
        # Computed properties
        assert notam.is_trigger_notam is True
        assert notam.is_drone_related is True
        assert notam.is_restriction is True
        assert not notam.is_closure  # Not a closure (restriction but not closure)
        
        # Score should be at least: trigger (-10) + drone (30) + restriction (20) = 40
        # Plus maybe scope? scope AW includes A? No, A is not in AW
        assert notam.priority_score >= 40
    
    def test_from_api_dict_replace_notam(self, sample_notamr):
        """Test parsing a NOTAMR."""
        notam = Notam.from_api_dict(sample_notamr)
        
        assert notam.notam_id == "R2198/25"
        assert notam.notam_type == NotamType.REPLACE
        assert notam.replaces_notam_id == "R1978/25"
        
        # Score should be: replace (+5) + drone (30) + restriction (20) = 55
        assert notam.priority_score >= 55
    
    def test_html_entity_decoding(self):
        """Test HTML entity decoding in body."""
        data = {
            "facilityDesignator": "TEST",
            "notamNumber": "T0001/25",
            "issueDate": "01/01/2025 0000",
            "startDate": "01/01/2025 0000",
            "endDate": "01/02/2025 0000",
            "icaoMessage": "T0001/25 NOTAMN\nE) TEST &apos;QUOTED&apos; &amp; ENTITY",
            "cancelledOrExpired": False
        }
        
        notam = Notam.from_api_dict(data)
        assert "'" in notam.body  # &apos; becomes '
        assert "&" in notam.body   # &amp; becomes &
    
    def test_is_permanent(self):
        """Test PERM handling."""
        data = {
            "facilityDesignator": "TEST",
            "notamNumber": "T0002/25",
            "issueDate": "01/01/2025 0000",
            "startDate": "01/01/2025 0000",
            "endDate": "PERM",
            "icaoMessage": "T0002/25 NOTAMN\nC) PERM\nE) PERMANENT CLOSURE",
            "cancelledOrExpired": False
        }
        
        notam = Notam.from_api_dict(data)
        assert notam.is_permanent is True
        assert notam.valid_to is None
    
    def test_priority_score_closure(self):
        """Test closure scoring."""
        data = {
            "facilityDesignator": "TEST",
            "notamNumber": "T0003/25",
            "issueDate": "01/01/2025 0000",
            "startDate": "01/01/2025 0000",
            "endDate": "01/02/2025 0000",
            "icaoMessage": "T0003/25 NOTAMN\nE) RWY 09/27 CLOSED",
            "cancelledOrExpired": False
        }
        
        notam = Notam.from_api_dict(data)
        assert notam.is_closure is True
        # Closure (50) + NEW (10) = 60
        assert notam.priority_score == 60
    
    def test_priority_score_drone_closure(self):
        """Test drone closure scoring."""
        data = {
            "facilityDesignator": "TEST",
            "notamNumber": "T0004/25",
            "issueDate": "01/01/2025 0000",
            "startDate": "01/01/2025 0000",
            "endDate": "01/02/2025 0000",
            "icaoMessage": "T0004/25 NOTAMN\nE) AIRPORT CLOSED DUE TO DRONE ACTIVITY",
            "cancelledOrExpired": False
        }
        
        notam = Notam.from_api_dict(data)
        assert notam.is_closure is True
        assert notam.is_drone_related is True
        # Closure (50) + Drone (30) + NEW (10) = 90
        assert notam.priority_score >= 90
    
    def test_summary_format(self):
        """Test summary generation."""
        data = {
            "facilityDesignator": "KATL",
            "notamNumber": "A1234/25",
            "airportName": "Hartsfield-Jackson",
            "issueDate": "01/01/2025 1200",
            "startDate": "01/01/2025 1200",
            "endDate": "01/02/2025 1200",
            "icaoMessage": "A1234/25 NOTAMN\nE) RWY 09R CLSD",
            "cancelledOrExpired": False
        }
        
        notam = Notam.from_api_dict(data)
        summary = notam.summary()
        
        assert "A1234/25" in summary
        assert "KATL" in summary
        assert "Hartsfield-Jackson" in summary
        assert "Priority Score:" in summary
        assert len(summary) > 0