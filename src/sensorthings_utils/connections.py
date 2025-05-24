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

# external
import dotenv
import lnetatmo
from paho.mqtt.client import Client as mqttClient

# internal
from .config import ROOT_DIR

# environment setup
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
    NETATMO_CLIENT_ID: str
    NETATMO_CLIENT_SECRET: str
    NETATMO_REFRESH_TOKEN: str

@dataclass
class TTSCredentials:
    ...

def _init_credentials(
    sensor_type: str,
    target: Path = ROOT_DIR / ".credentials",
    env: Path | None = ROOT_DIR / ".env",
    container_environment: bool = False,
    format_override: Callable[[str], str] = lambda x: x 
    ) -> SingleAppCredentialFile | MultiAppCredentialFile:
    """
    Write credential files for various sensor systems.

    The application will strictly load credentials from a .credentials dir
    which contains a number of .<sensor_type>.credentials files. Credentials
    may be stored directly in the .credentials dir or loaded from a .env. This
    function handles the writing of .credentials with the following paths being
    plausible:

        1. Creates a .credentials dir and file if none exists
        2. If in a Container environment, we expect the credentials to have 
            been passed in the `docker-compose`; note that since .credentials
            is a mounted volume 
    """
    credentials_file = target / ("." + sensor_type + ".credentials")
    if not credentials_file.exists():
        credentials_file.parent.mkdir(parents=True, exist_ok=True)
        logging.info(".credentials directory created.")
        credentials_file.touch(exist_ok=True)
        logging.info(".credentials file created.")
    else:
        logging.info(".credentials file exists")
    if (
        (env and
        os.path.getmtime(env) > os.path.getmtime(credentials_file)) or
        container_environment
        ):
        logging.info(
                ".env file is newer than .credentials. " +
                "Checking for credentials.")
        credentials = os.getenv(f"{sensor_type.upper()}" + "_CREDENTIALS")
        if not credentials and container_environment:
            raise FileNotFoundError(f"No {sensor_type} credentials found in continer environment!")
        if not credentials and not container_environment:
            raise FileNotFoundError(f"No {sensor_type} credentials found in .env!")
        with open(credentials_file, "a") as f:
            if credentials: f.write(format_override(credentials))
            logging.info(f"Wrote {sensor_type}.credentials file.")
            return credentials_file
    else:
        logging.info(".credentials are newer than .env, using those.")
        return credentials_file

# logging setup
logger = logging.getLogger("connections")

class CredentialedHTTPSensorConnection(ABC):
    """
    Connections to sensors which use credentials as their main form of auth.
    """

    def __init__(
        self,
        credentials_dir: Path = Path(f"{ROOT_DIR}/.credentials"),
        env_file: Path = Path(f"{ROOT_DIR}/.env"),
    ):
        self.credentials_dir = credentials_dir
        self.env_file = env_file

    @property
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
    def retrieve(self) -> Any:
        """Retrieve 'raw' data from a sensor connection."""
        pass


class CredentialedMQTTSensorConnection(ABC):
    """
    Connections to sensors which use credentials as their main form of auth.
    """

    def __init__(
        self,
        credentials_dir: Path = Path(f"{ROOT_DIR}/.credentials"),
        env_file: Path = Path(f"{ROOT_DIR}/.env"),
    ):
        self.credentials_dir = credentials_dir
        self.env_file = env_file
        self.payload_queue = queue.Queue()

    @property
    @abstractmethod
    def _credentials(
        self,
    ) -> CredentialFile:
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
    def retrieve(self) -> Any:
        """Retrieve observations from the queue."""
        pass


class NetatmoConnection(CredentialedHTTPSensorConnection):
    """
    Netamo HTTP connection class. Endpoint for communicating with Netamo API.
    """

    def __init__(
        self,
        credentials_dir: Path = Path(f"{ROOT_DIR}/.credentials"),
        env_file: Path = Path(f"{ROOT_DIR}/.env"),
    ):
        self.max_connection_retries = 10
        self.credentials_dir = credentials_dir
        self.env_file = env_file

    @property
    def _credentials(
        self,
    ) -> Dict[str, str]:
        """
        """
        netatmo_credentials_file = _init_credentials(
                "netatmo", 
                self.credentials_dir, 
                self.env_file,
                CONTAINER_ENVIRONMENT
            )
        with open(netatmo_credentials_file, "r") as f:
            netatmo_credentials = json.load(f)
        try:
            NetatmoCredentials(**netatmo_credentials)
        except:
            raise AttributeError("Netatmo credentials in wrong format! Check keys.")
        return netatmo_credentials

    @property
    def _auth(self) -> lnetatmo.ClientAuth:
        """Return a netatmo authentication token."""
        return lnetatmo.ClientAuth(credentialFile=self._credentials)

    def retrieve(self) -> List[Dict[str, Any]]:
        for attempt in range(self.max_connection_retries):
            try:
                netatmo_connection = lnetatmo.WeatherStationData(self._auth)
                return netatmo_connection.rawData
            # catching a type error is not strictly correct, see
            # PR: https://github.com/philippelt/netatmo-api-python/pull/100
            except (TimeoutError, TypeError) as e:
                if attempt == self.max_connection_retries - 1:
                    logging.critical(
                        f"Netatmo sensor link down {e} - NO DATA BEING COLLECTED."
                    )
                else:
                    logging.info(
                        "Netatmo time-out error, waiting and establishing new connection."
                        + f"Attempt {attempt} of {self.max_connection_retries}"
                    )
                    time.sleep(30)



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
        self.application_name = application_name
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.credentials_dir = credentials_dir
        self.env_file = env_file
        self.payload_queue = queue.Queue()

    @property
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
                "tts", 
                self.credentials_dir, 
                self.env_file,
                CONTAINER_ENVIRONMENT
            )
        with open(tts_credentials_file, "r") as f:
            tts_credentials = json.load(f)
        return tts_credentials

    @property
    def _auth(self) -> mqttClient:
        """Authenticate connections using credentials."""
        app_key = self._credentials[self.application_name]
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
        logging.info(f"Connected to {self.mqtt_host}/{self.application_name}")
        topic = f"v3/{self.application_name}/devices/+/up"
        client.subscribe(topic)
        client.loop_start()
        return None

    def retrieve(self, timeout: int = 10) -> Dict | None:
        """Return and empty payload queue."""
        try:
            return self.payload_queue.get(timeout=timeout)
        except queue.Empty:
            pass
