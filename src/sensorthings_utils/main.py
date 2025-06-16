# standard
from typing import List, Literal, Dict, Callable
import time
import threading
import logging

# external

# internal
from sensorthings_utils.config import SENSOR_CONFIG_FILES, FROST_ENDPOINT
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

def push_available(exclude: List[str] = ['']) -> None:
    logging.info(f"Sensor stream starts in 30s, pushing too: {FROST_ENDPOINT}")
    time.sleep(1)
    sensor_streams = set() 
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
        host = sensor_arrangement.host
        sensor_name = sensor_config.sensor_model 
        frost.initial_setup(sensor_arrangement)
        match sensor_name:
            case "netatmo_nsw03":
                sensor_streams.add(NetatmoConnection(application_name))
            case "milesight_tts":
                if not host:
                    raise ValueError(f"Expected a host for the MQTT sensor: {sensor_name}")
                sensor_streams.add(TTSConnection(application_name="multicare-bucharest@ttn", mqtt_host=host))
    for connection in set(sensor_streams):
        connection.start(push=True)

    logging.info(f"Started {threading.active_count()} threads: {[i.name for i in threading.enumerate()]}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for conn in sensor_streams:
            logging.info(f"Stopping thread for {conn.application_name}")
            conn.stop()

    logging.info("Successfully shutdown connections.")

if __name__ == "__main__":
   push_available() 

