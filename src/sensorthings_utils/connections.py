"""Manage connections, authentication & protocols with sensor infrastructure"""

# standard
import os
import logging
import json
from pathlib import Path
from typing import List, Any, Dict, Callable
from abc import ABC, abstractmethod
import time
from dataclasses import dataclass
import queue
from functools import cached_property
from urllib.error import URLError
import threading

# external
import dotenv
import lnetatmo
from paho.mqtt.client import Client as mqttClient

# internal
from .config import ROOT_DIR
from .sensor_support import netatmo_nws03, milesight_am308L, milesight_am103L
from .monitor import network_monitor

# environment setup
logger = logging.getLogger(__name__)
root_logger = logging.getLogger("rootLogger")
CONTAINER_ENVIRONMENT = True if os.getenv("CONTAINER_ENVIRONMENT") else False
# type definitions
SingleAppCredentialFile = Path
MultiAppCredentialFile = Path
CredentialFile = SingleAppCredentialFile | MultiAppCredentialFile
SingleAppCredentials = Dict[str, str]
MultiApplicationCredentials = List[Dict[str, str]]
Credentials = SingleAppCredentials | MultiApplicationCredentials


@dataclass
class NetatmoCredentials:
    CLIENT_ID: str
    CLIENT_SECRET: str
    REFRESH_TOKEN: str


@dataclass
class TTSCredentials: ...


def _init_credentials(
    application_name: str,
    sensor_type: str,
    target: Path = ROOT_DIR / ".credentials",
    env: Path = ROOT_DIR / ".env",
    format_override: Callable[[str], str] = lambda x: x,
) -> SingleAppCredentialFile | MultiAppCredentialFile:
    """
    Write credential files for various sensor systems.

    The application will load credentials from a .credentials dir which
    contains a number of .<sensor_type>.credentials files. Credentials may be
    stored directly in the .credentials dir or loaded from a .env. This
    function handles the writing of .credentials with the following paths being
    plausible, beggining by making the credentials file if it does not exist.
    From there, four paths are possible:

        The credential file **is** new:

            - a valid .env is found: credentials are copied over from the .env,
            raise an error if they're not valid.
            - no .env is found: assume they're loaded into the environment,
            raise error if they're not.

        The credential file is **not** new:

            - a valid .env is found: it will be copied over only if its newer
            than the credential file.
            - a valid .env is not found: just use the credentials there.

    This function exists in this complicated state because of containers. We
    never bake .env into container images, and they're preloaded using the
    env_file marker.
    """
    credentials_file = target / (f"{application_name}.{sensor_type}.credentials")
    if not credentials_file.exists():
        credentials_file.parent.mkdir(parents=True, exist_ok=True)
        credentials_file.touch(exist_ok=True)
        logger.info(f"{application_name}.{sensor_type}.credentials file created.")
        new_credential_file = True
    else:
        logger.info(f"{application_name}.{sensor_type}.credentials exists.")
        new_credential_file = False
    # new credential file and an .env exists (outside container environment)
    # so write the credentials from env.
    if new_credential_file and env.exists():
        # flush out environment variables currently loaded into the .env
        # this is mostly a testing issue.
        os.environ.pop(f"{sensor_type.upper()}_CREDENTIALS", None)
        logger.info(
            f"Environment exists, loading variables and writing to credentials."
        )
        dotenv.load_dotenv(env)
        all_credentials = os.getenv(f"{sensor_type.upper()}_CREDENTIALS")
        if all_credentials == None:
            raise ValueError(
                f"Environment file found, but {sensor_type.capitalize()} not found. "
                + "Cannot pass malformed or incomplete .env files."
            )
        all_credentials_json = json.loads(all_credentials)
        credentials = json.dumps(all_credentials_json.get(application_name))
        with open(credentials_file, "w") as f:
            f.write(format_override(credentials))
            logger.info(
                f"wrote credentials to {application_name}.{sensor_type}.credentials file."
            )
            return credentials_file
    # if a new credential file was made and .env does not exist (for container
    # enviornments) then we assume they're already loaded up, otherwise
    # exception.
    if new_credential_file and not env.exists():
        all_credentials = os.getenv(f"{sensor_type.upper()}_CREDENTIALS")
        if all_credentials == None:
            raise FileNotFoundError(
                f"No credentials found for '{sensor_type}': missing both "
                + "env file and container variable."
            )
        all_credentials_json = json.loads(all_credentials)
        credentials = json.dumps(all_credentials_json.get(application_name))
        with open(credentials_file, "w") as f:
            f.write(format_override(credentials))
            logger.info(
                f"wrote credentials to {application_name}.{sensor_type}.credentials file."
            )
            return credentials_file
    # if a credential file was already there and there is no env (for container
    # environments) then check if the credentials are there and use those
    # otherwise exception.
    if not new_credential_file and not env.exists():
        dotenv.load_dotenv(credentials_file)
        credentials = os.getenv(f"{sensor_type.upper()}_CREDENTIALS")
        if credentials == None:
            raise ValueError(
                f"Newer environment file found, but {sensor_type.capitalize()} not found. "
                + "Ensure key is in .env file!"
            )
        logger.info(
            f"{application_name}.{sensor_type}.credentials exist and no new .env was passed. "
            + "Using existing."
        )
        return credentials_file
    # if credential file was already there but an .env exists (outside of
    # container environments), check if it is newer, in which case we
    # overwrite.
    elif not new_credential_file and os.path.getmtime(env) > os.path.getmtime(
        credentials_file
    ):
        logger.info(
            ".env file is newer than .credentials. " + "Checking for credentials."
        )
        dotenv.load_dotenv(env)
        all_credentials = os.getenv(f"{sensor_type.upper()}_CREDENTIALS")
        if all_credentials == None:
            raise ValueError(
                f"Newer environment file found, but {sensor_type.capitalize()} not found. "
                + "Ensure key is in .env file!"
            )
        all_credentials_json = json.loads(all_credentials)
        credentials_json = all_credentials_json.get(application_name)
        credentials = json.dumps(credentials_json)
        with open(credentials_file, "w") as f:
            f.write(format_override(credentials))
            logger.info(
                f"wrote credentials to {application_name}.{sensor_type}.credentials file."
            )
            return credentials_file
    else:
        logger.info(
            f"{application_name}.{sensor_type}.credentials is newer than .env, using existing credentials."
        )
        return credentials_file


class CredentialedHTTPSensorConnection(ABC):
    """
    Connections to sensors which use credentials as their main form of auth.
    """

    def __init__(
        self,
        application_name: str,
        credentials_dir: Path = Path(f"{ROOT_DIR}/.credentials"),
        env_file: Path = Path(f"{ROOT_DIR}/.env"),
        max_retries: int = 10,
        interval: int = 300,
    ):
        self.application_name = application_name
        self.credentials_dir = credentials_dir
        self.env_file = env_file
        self.max_connection_retries = max_retries
        self.interval = interval
        self._thread = None
        self._stop_event = threading.Event()

    def __hash__(self) -> int:
        return hash(self.application_name)

    def __eq__(self, other) -> bool:
        if not isinstance(other, CredentialedHTTPSensorConnection):
            return False
        if other.application_name == self.application_name:
            return True
        else:
            return False

    @cached_property
    @abstractmethod
    def _credentials(
        self,
    ) -> SingleAppCredentialFile | MultiAppCredentialFile | Dict[str, str]:
        """
        Load and parse from environment variables and write
        them to a permanent credentials .<sensor_type>.credentials file,
        returning the file path.
        """
        pass

    @property
    @abstractmethod
    def _auth(
        self,
    ) -> Any:
        """Authenticate connections using credentials."""
        pass

    @abstractmethod
    def retrieve(self, push: bool = False) -> Any:
        """Retrieve 'raw' data from a sensor connection."""
        pass

    def start(self, push: bool = False):
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(
                target=self._loop, args=(push,), daemon=True, name=self.application_name
            )
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(5)

    def _loop(self, push: bool):
        restart_attempt = 0
        while not self._stop_event.is_set():
            try:
                self.retrieve(push)
                time.sleep(self.interval)
                restart_attempt = 0
            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                restart_attempt += 1
                time.sleep(300)
                logger.warning(
                    f"Thread {self.application_name} encountered an exception {e}. Sleeping and trying again."
                )
                if restart_attempt == self.max_connection_retries:
                    self.stop()
                    logger.critical(f"Thread {self.application_name} died: {e}")


# TODO: Consider a parent connection class.
class CredentialedMQTTSensorConnection(ABC):
    """
    Connections to sensors which use credentials as their main form of auth.
    """

    def __init__(
        self,
        application_name: str,
        mqtt_host: str,
        mqtt_port: int,
        credentials_dir: Path = Path(f"{ROOT_DIR}/.credentials"),
        env_file: Path = Path(f"{ROOT_DIR}/.env"),
        max_retries: int = 10,
    ):
        self.application_name = application_name
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.credentials_dir = credentials_dir
        self.env_file = env_file
        self.payload_queue = queue.Queue()
        self.subscribed: bool = False
        self._thread = None
        self._stop_event = threading.Event()
        self.max_retries = max_retries

    def __hash__(self) -> int:
        return hash(self.application_name)

    def __eq__(self, other) -> bool:
        if not isinstance(other, CredentialedMQTTSensorConnection):
            return False
        if other.application_name == self.application_name:
            return True
        else:
            return False

    @cached_property
    @abstractmethod
    def _credentials(
        self,
    ) -> Dict[str, str]:
        """
        Load, parse and write credentials from environment variables and write
        them to a permanent credentials .<sensor_type>.credentials file,
        returning the file path.
        """
        pass

    @property
    @abstractmethod
    def _auth(
        self,
    ) -> Any:
        """Authenticate connections using credentials."""
        pass

    @abstractmethod
    def subscribe(self) -> Any:
        """Subscribe to an MQTT sensor connection."""
        pass

    @abstractmethod
    def retrieve(self, push: bool = False) -> Any:
        """Retrieve 'raw' data from a sensor connection."""
        pass

    def start(self, push: bool = False):
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(
                target=self._loop, args=(push,), daemon=True, name=self.application_name
            )
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(5)

    def _loop(self, push: bool):
        restart_attempts = 0
        while not self._stop_event.is_set():
            try:
                self.retrieve(push)
                restart_attempts = 0
            except KeyboardInterrupt as e:
                self.stop()
                break
            except Exception as e:
                restart_attempts += 1
                time.sleep(300)
                logger.warning(
                    f"Thread {self.application_name} encountered an exception {e}. Sleeping and trying again."
                )
                if restart_attempts == self.max_retries:
                    self.stop()
                    logger.critical(f"Thread {self.application_name} has died: {e}.")


class NetatmoConnection(CredentialedHTTPSensorConnection):
    """
    Netamo HTTP connection class. Endpoint for communicating with Netamo API.
    """

    def __init__(
        self,
        application_name: str,
        credentials_dir: Path = Path(f"{ROOT_DIR}/.credentials"),
        env_file: Path = Path(f"{ROOT_DIR}/.env"),
        max_retries: int = 10,
        interval: int = 300,
    ):
        super().__init__(
            application_name=application_name,
            credentials_dir=credentials_dir,
            env_file=env_file,
            max_retries=max_retries,
            interval=interval,
        )

    @cached_property
    def _credentials(
        self,
    ) -> SingleAppCredentialFile:
        """
        Initialize, check and return netatmo credentials file.
        """
        netatmo_credentials_file = _init_credentials(
            self.application_name,
            "netatmo",
            self.credentials_dir,
            self.env_file,
        )
        with open(netatmo_credentials_file, "r") as f:
            netatmo_credentials = json.load(f)
        try:
            NetatmoCredentials(**netatmo_credentials)
        except:
            raise AttributeError(
                (
                    f"Netatmo credentials in wrong format! Got these keys: "
                    + f"{', '.join(netatmo_credentials.keys())} Expected: "
                    + f"CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN"
                )
            )
        return netatmo_credentials_file

    @property
    def _auth(self) -> lnetatmo.ClientAuth:
        """Return a netatmo authentication token."""
        return lnetatmo.ClientAuth(credentialFile=self._credentials)

    def retrieve(
        self,
        push: bool = False,
    ) -> List[Dict[str, Any]] | None:  # type: ignore
        """Retrieve the latest untransformed observation set (one or more) from the Netatmo API."""
        attempt = 0
        while attempt < self.max_connection_retries:
            try:
                netatmo_connection = lnetatmo.WeatherStationData(self._auth)
                attempt = 0
                if (payload := netatmo_connection.rawData) is None:
                    raise ValueError(
                        "Netatmo Payload for Sensor "
                        + f"{self.application_name} is empty."
                    )
                logger.info(
                    f"Received payload from Netatmo application "
                    + f"{self.application_name} from {len(payload)} sensors."
                )
                network_monitor.add_named_count(
                    "payloads_received", self.application_name, 1
                )
                if push:
                    netatmo_nws03.frost_upload(
                        payload, application_name=self.application_name
                    )
                    return None
                else:
                    return payload
            # catching a type error is not strictly correct, see
            # PR: https://github.com/philippelt/netatmo-api-python/pull/100
            except (TimeoutError, URLError, TypeError) as e:
                attempt += 1
                logger.info(
                    "Netatmo time-out error, waiting and establishing new connection. "
                    + f"Retrying attempt {attempt} of {self.max_connection_retries}."
                    + f"Error raised: {e}"
                )
                time.sleep(30)
                return list(dict())
        logger.warning(f"Netatmo sensor link down - NO DATA BEING COLLECTED.")


class TTSConnection(CredentialedMQTTSensorConnection):
    """
    TTS MQQT connection class. Endpoint for communicating with TheThings Stack.
    """

    def __init__(
        self,
        application_name: str,
        mqtt_host: str,
        mqtt_port: int = 8883,
        credentials_dir: Path = Path(f"{ROOT_DIR}/.credentials"),
        env_file: Path = Path(f"{ROOT_DIR}/.env"),
    ):
        super().__init__(
            application_name=application_name,
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            credentials_dir=credentials_dir,
            env_file=env_file,
        )

    @cached_property
    def _credentials(
        self,
    ) -> Dict[str, str]:
        """
        Return credentials from the `.tts.credentials` file.

        Parse or load environment variables and write them to a permanent
        credentials file for use later. TTS uses application names and API keys
        and a user may want to stream readings from more than one application.
        Thus the credential file will have the following format:

           {"<APP_NAME_1>":"<APP1_API_KEY>", ...}

        When passing credentials from a .env, format should be as follows:

            TTS_CREDENTIALS = {"<APP_NAME_1>":"<APP1_API_KEY>", ...}
        """
        tts_credentials_file = _init_credentials(
            self.application_name,
            "tts",
            self.credentials_dir,
            self.env_file,
        )
        with open(tts_credentials_file, "r") as f:
            tts_credentials = json.load(f)
        return tts_credentials

    @property
    def _auth(self) -> mqttClient:
        """Authenticate connections using credentials."""
        app_key = self._credentials["API_KEY"]
        client = mqttClient()
        # TTS usernames are equivalent to the application names.
        client.username_pw_set(self.application_name, app_key)
        client.tls_set()
        return client

    def subscribe(self) -> None:
        client = self._auth

        # put a retrieved payload in the queue.
        def on_message(client, userdata, message):
            self.payload_queue.put(json.loads(message.payload))

        client.on_message = on_message
        client.connect(self.mqtt_host, self.mqtt_port)
        logger.info(f"Connected to {self.mqtt_host}/{self.application_name}")
        topic = f"v3/{self.application_name}/devices/+/up"
        client.subscribe(topic)
        self.subscribed = True
        client.loop_start()
        return None

    # TODO: is 'retrieve' correct? This method retrieves but also transforms and pushes (through other functions.)
    # either come up with a better name or separate functionality.
    def retrieve(
        self,
        push: bool = False,
        timeout: int = 300,
        max_retries: int = 10,
    ) -> Dict | None:
        """Return and empty payload queue."""
        if not self.subscribed:
            self.subscribe()
        attempts = 1
        while attempts <= max_retries:
            retrieve_success = False
            try:
                payload_received = self.payload_queue.get(timeout=timeout)
                network_monitor.add_named_count(
                    "payloads_received", self.application_name, 1
                )
                attempts = 0 if payload_received else attempts
                logger.debug(f"{payload_received=}")
                sensor_model = (
                    payload_received.get("uplink_message", {})
                    .get("version_ids", {})
                    .get("model_id")
                )
                if not isinstance(sensor_model, str):
                    raise ValueError(
                        f"{self.application_name}: expected str sensor_model but got {sensor_model=}"
                    )
                logger.info(
                    f"Received payload from TTS application: "
                    + f"{self.application_name} from a {sensor_model} sensor."
                )
                if push:
                    match sensor_model:
                        case "am308l":
                            milesight_am308L.frost_upload(
                                payload_received, application_name=self.application_name
                            )
                        case "am103l":
                            milesight_am103L.frost_upload(
                                payload_received, application_name=self.application_name
                            )

                retrieve_success = True
                return payload_received
            except queue.Empty:
                logger.warning(
                    f"No data received from {self.application_name}"
                    + f"in {timeout} seconds, retry count: {attempts}."
                )
                attempts += 1
            if not retrieve_success:
                network_monitor.add_named_count(
                    "rejected_payloads", self.application_name, 1
                )
        raise TimeoutError(
            f"No messages retrieved for {self.application_name}."
            + f"Attempt {attempts} of {max_retries}."
        )
