"""FROST server support for Netatmo Sensor NWS03."""

# standard
import logging
import time
from typing import List, Dict, Any, Generator, Tuple

# internal
from .sensor_things.core import Observation
from .config import CONTAINER_ENVIRONMENT
from sensorthings_utils.frost import filter_query, make_frost_object
from .connections import NetatmoConnection

logger = logging.getLogger("netatmo")


def _filter(
    payload: List[Dict[str, Any]],
    exclude: List[str] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Return latest observations from all Netatmo weather stations.

    Raw data is lightly modified (organized) and warngled into a
    station-by-station format. Passing `station_ids` allows for filtering for
    specific station data.

    :param station_ids: Station IDs to filter by.
    :type station_ids: List[str]
    :return: Available netatmo sensors and their respective data.
    :rtype: Dict[str, Dict[str, str | int | float]]
    """
    data = {}
    if not payload[0]:
        logging.critical("No netatmo data returned.")
    if exclude:
       payload = [i for i in payload if i["_id"] not in exclude] 
    for item in payload:
        if item["reachable"] == False:
            logging.info(f"Netatmo Station {item["_id"]} is unreachable.")
            return data
        station_id = item["_id"]
        dashboard_data = item["dashboard_data"]
        dashboard_data["station_id"] = station_id
        data[station_id] = dashboard_data
    return data


# TODO: #7 Consider creating a standard namedTuple for returns.
def _transform(data: Dict[str, Any]) -> Generator[Tuple[Any, ...]]:
    """
    Transform data from a station into an standardized format.
    """
    NETATMO_TO_DATASTREAM_MAP = {
        "Temperature": "temperature_indoor",
        "CO2": "co2",
        "Humidity": "humidity",
        "Noise": "noise",
        "Pressure": "gauge_pressure",
        "AbsolutePressure": "absolute_pressure",
    }
    sensor_name = data["station_id"]
    result_time = data["time_utc"]  # type: ignore
    for observation_type, result_value in data.items():
        # there are a number of values in a response we're not interested in.
        if observation_type not in NETATMO_TO_DATASTREAM_MAP:
            continue
        datastream_name = NETATMO_TO_DATASTREAM_MAP[observation_type]
        yield (sensor_name, datastream_name, result_time, result_value)  # type: ignore


def stream(
        netatmo_connection: NetatmoConnection,
        exclude: List[str] | None = None,
        sleep_time: int = 240
    ) -> None:
    """Extract, transform and load Netatmo devices linked to your account."""
<<<<<<< HEAD
    payload = netatmo_connection.retrieve()
    for station in _filter(payload, exclude).values():
        observation_stream = _transform(station)
=======
    for data in _extract().values():
        if not data:
            logging.info(f"No data.")
        observation_stream = _transform(data)
>>>>>>> origin/main
        for o in observation_stream:
            sensor_name = o[0]
            datastream_name = o[1]
            phenomenon_time = o[2]
            result = o[3]

            sensor_datastreams = filter_query(
                entity="/Sensors",
                filter_string=f"name eq '{sensor_name}'",
                url=None,
                container_environment=CONTAINER_ENVIRONMENT,
            )
            try:
                sensor_datastreams = sensor_datastreams["value"][0][
                    "Datastreams@iot.navigationLink"
                ]  # url of datastreams #type: ignore

                datastream = filter_query(
                    entity=None,
                    filter_string=f"name eq '{datastream_name}'",
                    url=sensor_datastreams,
                )  # type: ignore

                push_link = datastream["value"][0]["Observations@iot.navigationLink"]
                observation = Observation(
                    result=result,
                    phenomenonTime=phenomenon_time,
                )
                observation = make_frost_object(observation, push_link)
            except IndexError:
                logging.critical(
                    f"Failure adding observation/s for {sensor_name}. Has the datastream been set up?"
                )
                break
    time.sleep(sleep_time)
