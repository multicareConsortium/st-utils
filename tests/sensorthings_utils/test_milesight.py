"""Test Milesight support Module."""
#standard
import pytest
import json
#external
#internal
import sensorthings_utils.milesight as milesight
from sensorthings_utils.config import TEST_DATA_DIR

@pytest.fixture
def am3081_tts_payload() -> dict:
    """Milesight-iot-am308l payload pushing to a TheThingsStack LoRa Webserver."""
    data_path = TEST_DATA_DIR / "milesight_tts_payload.json"
    with open(data_path , "r") as f:
        payload = json.load(f)
        return payload

@pytest.fixture
def am3081_tts_observations() -> dict:
    observations = {
        "battery": 95,
        "co2": 828,
        "humidity": 61,
        "light_level": 1,
        "pir": "idle",
        "pm10": 477,
        "pm2_5": 469,
        "pressure": 1011.3,
        "temperature": 25,
        "tvoc": 4.84
      }
    return observations 

@pytest.fixture
def am3081_tts_transformed_observations() -> dict:
    observations = {
        "battery_level": 95,
        "co2": 828,
        "humidity": 61,
        "light_level": 1,
        "passive_infrared": "idle",
        "particulate_matter_10": 477,
        "particulate_matter_2_5": 469,
        "gauge_pressure": 1011.3,
        "indoor_temperature": 25,
        "total_volatile_organic_compounds": 4.84
      }
    return observations 

    MILESIGHT_TO_DATASTREAM_MAP = {
        "battery": "battery_level",
        "co2": "co2",
        "humidity": "humidity",
        "light_level": "light_level",
        "pir": "passive_infrared",
        "pm10": "particulate_matter_10",
        "pm2_5": "particulate_matter_2_5",
        "pressure": "gauge_pressure",
        "temperature": "indoor_temperature",
        "tvoc": "total_volatile_organic_compounds",
    }

class TestFilter:

    def test_filter(self, am3081_tts_payload, am3081_tts_observations):
        filtered_payload = milesight._filter(am3081_tts_payload)
        assert isinstance(filtered_payload, dict)
        for k in milesight.EXPECTED_KEYS:
            assert k in filtered_payload
        assert filtered_payload["sensor_name"] == "24E124707E427251"
        assert filtered_payload["phenomenon_time"] == "2025-05-31T15:34:13.536993Z"
        assert filtered_payload["observations"] == am3081_tts_observations

    def test_transform(self, am3081_tts_payload, am3081_tts_transformed_observations):
        transformed_payload = milesight._transform(milesight._filter(am3081_tts_payload))
        assert isinstance(transformed_payload, dict)
        for k in milesight.EXPECTED_KEYS:
            assert k in transformed_payload
        assert transformed_payload["sensor_name"] == "24E124707E427251"
        assert transformed_payload["phenomenon_time"] == "2025-05-31T15:34:13.536993Z"
        assert transformed_payload["observations"] == am3081_tts_transformed_observations

