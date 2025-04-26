"""Support for Milesight LoRaWan x TheThingsNetwork Sensors"""

# standard
import os
from pathlib import Path
from typing import Dict, List, Any
# external

# internal
from .config import CREDENTIALS_DIRECTORY

# environment setup
CONTAINER_ENVIRONMENT = True if os.getenv("CONTAINER_ENVIRONMENT") else False
TTN_CREDENTIALS_PATH = Path(CREDENTIALS_DIRECTORY / ".ttn.credentials")


def _extract(
    dev_eui: List[str] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Return latest observations from all TheThingsNetwork LoRaWan devices.

    :param dev_euis: Device DevEUI (device extended unique identifier)
    :type dev_euis: List[str]
    :return: Dict with DevEUI as keys and values as nested Dict.
    :rtype: Dict[str, Dict[str, str | int | float]]
    """
    data = {}
    # extraction logic goes here.
    return data


def _transform(data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Return transformed observations.

    :param data: Raw data from Milesight sensor.
    :type data:
    :return:
    :rtype:
    """
    ...


def _load():
    pass
