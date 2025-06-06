"""
Extensions and wrappers to facilitate OGC SensorThings compliant implementations.
"""

# standard
from typing import Dict, List, Any, Type, Literal, Optional, Tuple, TYPE_CHECKING
from pathlib import Path
import logging
# external
import yaml

# internal
from .core import (
    Sensor,
    Thing,
    Datastream,
    Location,
    ObservedProperty,
    SensorThingsObject,
    SENSOR_THINGS_OBJECTS,
)

# typing and type-checking
if TYPE_CHECKING:
    ...

__all__ = ["SensorConfig", "SensorArrangement"]

logger = logging.getLogger(__name__)

class SensorConfig:
    """
    Dict-like sensor-configuration structure. Use square bracket indexing to
    return values. 

    Class is responsible for parsing, validating and serving sensor 
    configuration.
    """

    def __init__(self, filepath: str | Path) -> None:
        self._filepath = Path(filepath)
        self._data: Dict[str, Any] = self._load()
        # public:
        self.sensor_model = self["networkMetadata"]["sensor_model"] 
        self.data = self.validate()

    def _load(self) -> Dict:
        with open(self._filepath, "r") as file:
            data = yaml.safe_load(file)
        return data

    def __getitem__(self, key) -> Any:
        return self._data.get(key)

    def validate(self) -> Dict[str, Any]:
        unvalidated_data = self._load()
        if not all(
                [self._validate_sensor_name(unvalidated_data),
                 self._validate_entity_contents(unvalidated_data),
                 self._validate_linking_sensor(unvalidated_data),
                 self._validate_sensor_and_things_have_datastreams(unvalidated_data)]
                ):
            logger.error(f"{self._filepath.name} is an invalid config.")
            return {}
        valid_data = unvalidated_data
        return valid_data

    def _validate_sensor_name(self, uv_data: Dict) -> bool:
        """Validate sensor key and sensor name (attribute) matches."""

        sensor_config = uv_data.get("sensors")
        if sensor_config is None:
            logger.error(f"No 'sensors' key in SensorConfig {self._filepath.name}.")
            return False

        sensor_key = next(iter(sensor_config))
        sensor_name = sensor_config.get(sensor_key).get("name")

        if len(sensor_config) != 1:
            logger.error(f"SensorConfig {self._filepath.name} should have exactly one sensor.")
            return False
        if sensor_key != sensor_name:
            logger.error(f"SensorConfig {self._filepath.name}'s name ({sensor_name}) does not match its primary key {sensor_key}.")
            return False

        return True

    def _validate_entity_contents(self, unvalidated_data:Dict) -> bool:
        "Check that primary sensor things keys are there, and that the contents are as expected."
        expected_classes = [
                "sensors",
                "things",
                "locations",
                "datastreams",
                "observedProperties",
                ] 
        expected_class_fields = {
                "sensors": {
                    "name":str,
                    "description":(str, dict),
                    "properties":(str, dict),
                    "encodingType":str,
                    "metadata":str,
                    "iot_links":dict
                    },
                "things": {
                    "name": str,
                    "description": str,
                    "properties": (str, type(None)),
                    "iot_links": dict
                    },
                "locations": {
                    "name":str,
                    "description":str,
                    "properties": (str, type(None)),
                    "encodingType": str,
                    "location":dict,
                    "iot_links":dict
                    },
                "datastreams": {
                    "name": str, "description": str, 
                    "observationType": str,
                    "unitOfMeasurement":dict,
                    "observedArea":dict,
                    "phenomenon_time": (str, type(None)),
                    "result_time": (str, type(None)),
                    "properties": (dict, type(None)),
                    "iot_links": dict
                    },
                "observedProperties": {
                    "name":str,
                    "definition":str,
                    "description":str,
                    "properties": (str, type(None))
                    },
                }
        # entity is going to be sensors, things, locations, etc.
        invalid = False 
        for cls in expected_classes:
            if (actual_entity:= unvalidated_data.get(cls)) is None:
                logger.error(f"Missing primary key: {cls}. Will not continue with validation.")
                return False
            # item is going to be each entry, e.g., 70:33:50.. (sensor), "apartment" (location)
            expected_field_keys = set(expected_class_fields[cls].keys())
            for field_key in actual_entity: 
                actual_field_keys = set(actual_entity[field_key].keys())
                missing_field_keys= expected_field_keys - actual_field_keys
                extra_field_keys = actual_field_keys - expected_field_keys
                if missing_field_keys:
                    logger.error(
                            f"{cls}.{field_key} has missing keys: {missing_field_keys}."
                            )
                    invalid = True
                if extra_field_keys:
                    logger.error(
                            f"{cls}.{field_key} has extra keys: {extra_field_keys}."
                            )
                    invalid = True
                for field in actual_entity[field_key]:
                    expected_type = expected_class_fields[cls][field]
                    if not isinstance(
                            actual_entity[field_key][field],
                            expected_type
                            ):
                        logger.error(
                                f"{cls}.{field_key}.{field} is of the wrong type "
                                + f"expected {expected_type}, got {type(actual_entity[field_key][field])}"
                                )
                        invalid = True

        return True if not invalid else False

    def _validate_linking_sensor(self, unvalidated_data:Dict[str, Dict[str, Any]]) -> bool:
        """Sensor name should be present in each datastream."""
        sensor_name = next(iter(unvalidated_data["sensors"]))
        passed_datastreams = unvalidated_data["datastreams"]
        for datastream in passed_datastreams:
            datastream_contents = passed_datastreams[datastream]
            if datastream_contents["iot_links"]["sensors"][0] != sensor_name:
                logger.error(f"{self._filepath.name}'s {datastream} is missing reference to {sensor_name}.")
                return False

        return True
    
    def _validate_sensor_and_things_have_datastreams(self, unvalidated_data: Dict[str, Dict[str,Any]]) -> bool:
        """A sensor should have datastreams and these should be the same as the datastreams in the config."""
        actual_datastreams = set(unvalidated_data["datastreams"])
        invalid = False
        for s in ["sensors", "things"]:
            for entity in unvalidated_data[s]:
                passed_datastreams = unvalidated_data[s][entity]["iot_links"]["datastreams"] 
                if not isinstance(passed_datastreams, list):
                    logger.error(f"{self._filepath.name}'s {s} entity has iot_links which are not a list.")
                missing_datastreams = set(passed_datastreams) - actual_datastreams 
                extra_datastreams = actual_datastreams - set(passed_datastreams)
                if missing_datastreams:
                    logger.error(f"{self._filepath.name}'s {s} entity is missing datastream keys: {missing_datastreams}.")
                    invalid = True
                if extra_datastreams:
                    logger.error(f"{self._filepath.name}'s {s} entity is missing datastream keys: {extra_datastreams}.")
                    invalid = True

        return True if not invalid else False


        

class SensorArrangement:
    """
    Represents a single instance of the OGC SenorThings data model.

    An aggregation of 1 Sensor and 0 or more Things, Locations, Datastreams and
    ObservedProperties. Adherence to the datamodel implies this class includes: 1 Sensor,
    which may is linked to 0..* Datastreams. Each datastream is associated to 1 Thing
    and 1 ObservedProperty respectively. A Thing is associated with 0..* Locations. The
    class attributes consistently uses the plural form (i.e., sensors, things,
    datastreams etc.) although it will always include ONE sensor.
    """

    class_mappings: Dict[str, Type["SensorThingsObject"]] = {
        "sensors": Sensor,
        "things": Thing,
        "locations": Location,
        "datastreams": Datastream,
        "observedProperties": ObservedProperty,
    }

    name_mappings: Dict[
        str, Literal["Sensor", "Thing", "Location", "Datastream", "ObservedProperty"]
    ] = {
        "sensors": "Sensor",
        "things": "Thing",
        "locations": "Location",
        "datastreams": "Datastream",
        "observedProperties": "ObservedProperty",
    }

    def __init__(self, sensor_config: "SensorConfig"):
        self._sensor_config = sensor_config
        self._unlinked_arrangement: List["SensorThingsObject"] = self._initial_setup()
        # public:
        self.linked_arrangement: Tuple[SensorThingsObject, ...] = self._link_iot()
        self.application_name: str = ''
        self.host: str | None = None
        self._set_network_attributes()

    def __repr__(self) -> str:
        return (
            f"SensorArrangement (Sensor={self.get_entities("Sensor")[0].name}, "
            + f"SensorThingsObjects={len(self.linked_arrangement)})"
        )

    def _set_network_attributes(self) -> None:
        """Set the network attributes from the config file."""
        for network_attribute in ["application_name", "host"]:
            setattr(
                    self, 
                    network_attribute, 
                    self._sensor_config["networkMetadata"][network_attribute]
                    )

    def _initial_setup(self) -> List[SensorThingsObject]:
        """
        Return an unlinked list of SensorThingsObjects inferred from the class `arrangement_map`.

        Unpack the SensorConfig, unpack values into SensorThings objects.
        """
        unlinked_arrangement = []
        arrangement_map = self._sensor_config
        for entity in SENSOR_THINGS_OBJECTS:
            names = [_ for _ in arrangement_map[entity].keys()]
            for i in names:
                unlinked_arrangement.append(
                    SensorArrangement.class_mappings[entity](
                        **arrangement_map[entity][i]
                    )
                )
        return unlinked_arrangement

    def _link_iot(self) -> Tuple[SensorThingsObject, ...]:
        """Replace str representations of iot_links with SensorThingsObjects."""
        unlinked_arrangement = self._unlinked_arrangement
        for sensor in unlinked_arrangement:
            for entity, instances in sensor.iot_links.items():
                for idx, i in enumerate(instances):
                    e = self.name_mappings[entity]
                    sensor.set_iot_link(entity, i, self.get(e, instance=i))
        return tuple(unlinked_arrangement)

    def get(
        self,
        entity: Literal[
            "Sensor", "Thing", "Location", "Datastream", "ObservedProperty"
        ],
        instance: str,
        field: Optional[str] = None,
    ) -> SensorThingsObject:
        # this method is first called in the _link_iot function, before
        # self.linked_arrangement has been declared, so:
        query_arrangement = self._unlinked_arrangement or self.linked_arrangement
        for sensor_things_object in query_arrangement:
            if (
                sensor_things_object.__class__.__name__ == entity
                and sensor_things_object.name == instance
            ):
                if field:
                    return sensor_things_object.__dict__[field]
                elif not field:
                    return sensor_things_object  # type: ignore

        raise KeyError(f"Keys {entity}, {field} and {instance} not found.")

    def get_entities(
        self,
        entity: Literal[
            "Sensor", "Thing", "Location", "Datastream", "ObservedProperty"
        ],
    ) -> List["SensorThingsObject"]:
        entity_list = []
        for sensor_things_object in self.linked_arrangement:
            if sensor_things_object.__class__.__name__ == entity:
                entity_list.append(sensor_things_object)
        return entity_list
