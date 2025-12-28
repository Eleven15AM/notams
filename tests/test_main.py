import pytest
from src.main import NotamMonitor
# from src.config import Config

class TestNotamMonitor:
    """Test cases for NotamMonitor"""

    @pytest.fixture
    def monitor(self):
        """Create monitor instance"""
        return NotamMonitor()
    
    def test_parse_software_version(self,monitor):
        """Test that VERSION is not v0.0.0 when .env is loaded"""
        version = monitor.config.VERSION
        assert version is not None
        assert version != "v0.0.0"