"""Test sensor_things/extensions.py"""
# standard
from pathlib import Path
# external
import pytest
# internal
from sensorthings_utils.sensor_things.extensions import SensorConfig
from sensorthings_utils.config import TEST_DATA_DIR

@pytest.fixture
def good_config():
    path = TEST_DATA_DIR / "complete_sensor_config.yaml" 
    return path

class TestSensorConfig:
    """Test the SensorConfig class."""

    def test_good_config_validates(self, good_config):
        sensor_config = SensorConfig(good_config)
