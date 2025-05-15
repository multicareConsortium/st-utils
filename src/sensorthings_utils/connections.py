"""Manage connections, authentication & protocols with sensor infrastructure"""

# standard
import os
import logging
import json
from pathlib import Path
from typing import List, Any, Dict
from abc import ABC, abstractmethod
import time
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


def _write_credentials_file(
    credentials: Dict,
    credentials_file: SingleAppCredentialFile | MultiAppCredentialFile,
) -> None:
    """
    Write a single or multi application credential file.

    A single application file usually includes on application identifier and
    one set of keys, an exmaple of this is Netatmo, where sensors are associated
    with a user rather than an application. A multi application file will
    associate multiple applications with their own respective keys, for
    example as found in TheThingsStack.
    """
    credentials_file.parent.mkdir(mode=711, parents=True, exist_ok=True)
    with open(credentials_file, "w") as f:
        json.dump(credentials, f, indent=4)
    return None


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
    ) -> SingleAppCredentialFile:
        """
        Return path to a .<sensor_type>.credentials file.

        Parse or load environment variables and write them to a permanent
        credentials file. Rewrites .credentials file if .env is newer.
        """
        # Since the .env file is not baked into container image, only load the .env
        # outside of a container environment otherwise it is assumed that the
        # credentials are available as an env variable.
        if not CONTAINER_ENVIRONMENT:
            dotenv.load_dotenv(self.env_file)
        netatmo_client_id = os.getenv("NETATMO_CLIENT_ID")
        netatmo_client_secret = os.getenv("NETATMO_CLIENT_SECRET")
        netatmo_refresh_token = os.getenv("NETATMO_REFRESH_TOKEN")
        if not all([netatmo_client_id, netatmo_client_secret, netatmo_refresh_token]):
            raise FileNotFoundError(
                "No or incomplete Netatmo credentials found. "
                + "Where you expecting them? Check environment variables."
            )
        netatmo_credentials: SingleAppCredentials = {
            "CLIENT_ID": netatmo_client_id,
            "CLIENT_SECRET": netatmo_client_secret,
            "REFRESH_TOKEN": netatmo_refresh_token,
        }  # type: ignore (value error would be raised if not str)
        netatmo_credentials_file: SingleAppCredentialFile = Path(
            self.credentials_dir / ".netatmo.credentials"
        )
        if not netatmo_credentials_file.exists():
            _write_credentials_file(netatmo_credentials, netatmo_credentials_file)
            logging.info("Netatmo credential file written.")
            return netatmo_credentials_file
        if self.env_file.exists() and netatmo_credentials_file.exists():
            if os.path.getmtime(self.env_file) > os.path.getmtime(
                netatmo_credentials_file
            ):
                _write_credentials_file(netatmo_credentials, netatmo_credentials_file)
                logging.info("Netatmo credential file updated.")
        return netatmo_credentials_file

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
    ) -> MultiAppCredentialFile:
        """
        Return path to a `.tts.credentials` file.

        Parse or load environment variables and write them to a permanent
        credentials file for use later. TTS uses application names and API keys
        and a user may want to stream readings from more than one application.
        Thus the credential file will have the following format:

           {"<APP_NAME_1>":"<APP1_API_KEY>", ...}

        When passing credentials from a .env, format should be as follows:

            TTS_CREDENTIALS = {"<APP_NAME_1>":"<APP1_API_KEY>", ...}
        """
        tts_credentials_file: MultiAppCredentialFile = Path(
            self.credentials_dir / ".tts.credentials"
        )

        # Since the .env file is not baked into container image, only load the
        # .env outside of a container environment otherwise it is assumed that
        # the credentials are available as an env variable.
        if not CONTAINER_ENVIRONMENT:
            dotenv.load_dotenv(self.env_file)
        tts_credentials = os.getenv("TTS_CREDENTIALS")
        if not tts_credentials:
            raise FileNotFoundError(
                "No or incomplete TheThingsStack credentials found. "
                + "Where you expecting them? Check environment variables."
            )
        tts_credentials = json.loads(tts_credentials)
        if not tts_credentials_file.exists():
            _write_credentials_file(tts_credentials, tts_credentials_file)
            logging.info("TheThingsNetwork credential file written.")
            return tts_credentials_file
        if self.env_file.exists() and tts_credentials_file.exists():
            if os.path.getmtime(self.env_file) > os.path.getmtime(tts_credentials_file):
                _write_credentials_file(tts_credentials, tts_credentials_file)
                logging.info("TheThingsNetwork credential file updated.")
        return tts_credentials_file

    @property
    def _auth(self) -> mqttClient:
        """Authenticate connections using credentials."""
        with open(self._credentials, "r") as f:
            app_creds = json.load(f)
            app_key = app_creds[self.application_name]
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
