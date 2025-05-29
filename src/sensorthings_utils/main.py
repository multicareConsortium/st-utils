# standard
from typing import List, Literal, Dict, Callable
import time
import threading
import logging

# external

# internal
from sensorthings_utils.config import SENSOR_CONFIG_FILES
from sensorthings_utils import netatmo
from sensorthings_utils.sensor_things.extensions import (
    SensorArrangementMap,
    SensorArrangement,
)
from sensorthings_utils.frost import initial_setup
from sensorthings_utils.connections import NetatmoConnection, TTSConnection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def stream_available(exclude: List[str] | None = None, applications: List[str] | None = None) -> None:
    logging.info("Sensor stream starts in 30s.")
    time.sleep(3)
    sensor_streams = set() 
    # commented out until SensorArrangementMap is ready
    # for f in SENSOR_CONFIG_FILES:
    #    sensor_arrangement_map = SensorArrangementMap(f)
    #    sensor_arrangement = SensorArrangement(sensor_arrangement_map)
    #    sensor_model = initial_setup(sensor_arrangement)
        # TODO: implement application info in SensorArrangementMap
        # application_name = sensor_arrangement.application_name 
        # application_host = sensor_arrangement.application_hist
    # This data is UNCONVERTED.
    for sensor_model in ["netatmo", "milesight-tts"]:
        match sensor_model:
            case "netatmo":
                #TODO: connections need to be hashable for sets
                sensor_streams.add(NetatmoConnection(application_name="tudelft-dt"))
            case "milesight-tts":
                sensor_streams.add(TTSConnection(application_name="multicare-bucharest@ttn", mqtt_host="eu1.cloud.thethings.network"))
                sensor_streams.add(TTSConnection(application_name="multicare-acerra@ttn", mqtt_host="eu1.cloud.thethings.network"))
    for connection in sensor_streams:
        connection.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for conn in sensor_streams:
            logging.info(f"Stopping thread for {conn.application_name}")
            conn.stop()

if __name__ == "__main__":
   stream_available() 

