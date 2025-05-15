"""Support for Milesight LoRaWan x TheThingsNetwork Sensors"""

# standard
import os
from pathlib import Path
from typing import Dict, List, Any
# external

# internal
from .connections import TTSConnection

# environment setup
CONTAINER_ENVIRONMENT = True if os.getenv("CONTAINER_ENVIRONMENT") else False


def _filter(payload: Dict, exclude: List[str] | None = None) -> Dict[str, Any] | None:
    """
    Parse and filter relevant observation data from Milesight Sensors.
    """
    data = {}
    device_id = payload["end_device_ids"]["device_id"]  # type: str
    if exclude and device_id in exclude:
        return None
    data["device_id"] = device_id
    data["result_time"] = payload["uplink_message"]["settings"]["time"]
    data.update(payload["uplink_message"]["decoded_payload"])
    return data


def _transform(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return transformed observations.

    :param data: Raw data from Milesight sensor.
    :type data:
    :return:
    :rtype:
    """
    ...
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

    for observation_type, result_value in data.items():
        if observation_type not in MILESIGHT_TO_DATASTREAM_MAP:
            continue
        datastream_name = MILESIGHT_TO_DATASTREAM_MAP[observation_type]
        yield (data["device_id"], datastream_name, data["result_time"], result_value)  # type: ignore


def _load():
    pass


def stream():
    pass
