# standard
from typing import List, Optional
import time
import threading
import logging
import os
# external

# internal
from sensorthings_utils.config import SENSOR_CONFIG_FILES, FROST_ENDPOINT_DEFAULT
from sensorthings_utils.sensor_things.extensions import (
    SensorConfig,
    SensorArrangement,
)
import sensorthings_utils.frost as frost
from sensorthings_utils.connections import NetatmoConnection, TTSConnection

logger = logging.getLogger(__name__)

# logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s:%(lineno)d]: %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def push_available(
        exclude: Optional[List[str]] = None,
        frost_endpoint: Optional[str] = None 
        ) -> None:
    """
    Push available sensor connections.

    :param exclude: Sensor's (MAC addresses) to exclude form the stream, 
        defaults to None.
    :type exclude: List[str] | None
    :param frost_endpoint: Endpointt to push to, defaults to FROST_ENDPOINT 
        set up in src/config.py (usually localhost)
    :type frost_endpoint: str | None
    """
    exclude = exclude or []
    frost_endpoint = frost_endpoint or os.getenv("FROST_ENDPOINT") or FROST_ENDPOINT_DEFAULT
    os.environ["FROST_ENDPOINT"] = frost_endpoint
    logging.info(f"Sensor stream starts in 30s, pushing too: {frost_endpoint}")
    time.sleep(1)
    sensor_connections = set() 
    for f in SENSOR_CONFIG_FILES:
        if f.name in exclude:
            continue
        sensor_config = SensorConfig(f)
        if not sensor_config.is_valid:
            logger.error(f"{f} is an invalid sensor configuration file!")
            logger.error(f"Skipping {f}, data from this sensor is not being processed.")
            continue
        sensor_arrangement = SensorArrangement(sensor_config)
        application_name = sensor_arrangement.application_name 
        logging.debug(f"{application_name=}")
        host = sensor_arrangement.host
        frost.initial_setup(sensor_arrangement)
        match host:
            case "netatmo":
                sensor_connections.add(NetatmoConnection(application_name))
            case _ if host.endswith(".thethings.network"):
                sensor_connections.add(
                        TTSConnection(
                            application_name=application_name,
                            mqtt_host=host,
                            )
                        )

    for connection in set(sensor_connections):
        connection.start(push=True)

    logging.info(f"Started {threading.active_count()} threads: {[i.name for i in threading.enumerate()]}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for conn in sensor_connections:
            logging.info(f"Stopping thread for {conn.application_name}")
            conn.stop()

    logging.info("Successfully shutdown connections.")

if __name__ == "__main__":
   push_available() 

