"""Manage connections, authentication & protocols with sensor infrastructure"""

# standard
import os
import logging
import json
from pathlib import Path
from typing import List, Any, Dict
from abc import ABC, abstractmethod
import time

# external
import dotenv
import lnetatmo

# internal
from .config import CREDENTIALS_DIRECTORY, MAX_CONNECTION_RETRIES, ENV_FILE

# environment setup
CONTAINER_ENVIRONMENT = True if os.getenv("CONTAINER_ENVIRONMENT") else False
# credential files for supported sensors / infrastructure


def _write(credentials: Dict, credentials_file: Path) -> None:
    """Write a credential file."""
    with open(credentials_file, "w") as f:
        json.dump(credentials, f, indent=4)
    return None


class SensorConnection(ABC):
    """
    Generic type representing any connection with a sensor network.
    """
    
    @abstractmethod
    def retrieve(self) -> Dict:
        pass


def _get_netatmo_creds() -> Path:
    """
    Return Netatmo credentials file path.

    Load environment variables, write or update a credential file. Returns path
    to file if validation does not raise problems.
    """
    # Since the .env file is not baked into container image, only load the .env outside
    # of a container environment.
    netatmo_credentials_file = Path(CREDENTIALS_DIRECTORY / ".netatmo.credentials")

    # Since the .env file is not baked into container image, only load the .env
    # outside of a container environment otherwise it is assumed that the
    # credentials are available as an env variable.

    if not CONTAINER_ENVIRONMENT:
        dotenv.load_dotenv(ENV_FILE)
    NETATMO_CLIENT_ID = os.getenv("NETATMO_CLIENT_ID")
    NETATMO_CLIENT_SECRET = os.getenv("NETATMO_CLIENT_SECRET")
    NETATMO_REFRESH_TOKEN = os.getenv("NETATMO_REFRESH_TOKEN")
    if not all([NETATMO_CLIENT_ID, NETATMO_CLIENT_SECRET, NETATMO_REFRESH_TOKEN]):
        raise FileNotFoundError(
            "No or incomplete Netatmo credentials found. "
            + "Where you expecting them? Check environment variables."
        )
    netatmo_credentials = {
        "CLIENT_ID": NETATMO_CLIENT_ID,
        "CLIENT_SECRET": NETATMO_CLIENT_SECRET,
        "REFRESH_TOKEN": NETATMO_REFRESH_TOKEN,
    }
    if not netatmo_credentials_file.exists():
        _write(netatmo_credentials, netatmo_credentials_file)
        logging.info("Netatmo credential file written.")
        return netatmo_credentials_file
    if ENV_FILE.exists() and netatmo_credentials_file.exists():
        if os.path.getmtime(ENV_FILE) > os.path.getmtime(netatmo_credentials_file):
            _write(netatmo_credentials, netatmo_credentials_file)
            logging.info("Netatmo credential file updated.")
        return netatmo_credentials_file


def _get_ttn_creds() -> Path:
    """
    Return TTN credentials file path.

    Load environment variables, write or update a credential file. Returns path
    to file if validation does not raise problems.

    """
    ttn_credentials_file = Path(CREDENTIALS_DIRECTORY / ".ttn.credentials")

    # Since the .env file is not baked into container image, only load the .env
    # outside of a container environment otherwise it is assumed that the
    # credentials are available as an env variable.

    if not CONTAINER_ENVIRONMENT:
        dotenv.load_dotenv(ENV_FILE)
    ttn_credentials = os.getenv("TTN_CREDENTIALS")
    if not ttn_credentials:
        raise FileNotFoundError(
            "No or incomplete Netatmo credentials found. "
            + "Where you expecting them? Check environment variables."
        )
    ttn_credentials = json.loads(ttn_credentials)
    if not ttn_credentials_file.exists():
        _write(ttn_credentials, ttn_credentials_file)
        logging.info("TheThingsNetwork credential file written.")
        return ttn_credentials_file
    if ENV_FILE.exists() and ttn_credentials_file.exists():
        if os.path.getmtime(ENV_FILE) > os.path.getmtime(ttn_credentials_file):
            _write(ttn_credentials, ttn_credentials_file)
            logging.info("TheThingsNetwork credential file updated.")
        return ttn_credentials_file


# logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s: %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ttn")


class NetatmoConnection(SensorConnection):
    """ 
    Netamo HTTP connection class. Endpoint for communicating with Netamo API.
    """
    def __init__(self):
        self.max_connection_retries = 10

    def retrieve(
        self,
        sensor: List[str] | None = None,
    ) -> Any:
        netatmo_credentials_file = _get_netatmo_creds()
        auth = lnetatmo.ClientAuth(credentialFile=netatmo_credentials_file)

        for attempt in range(MAX_CONNECTION_RETRIES):
            try:
                netatmo_connection = lnetatmo.WeatherStationData(auth)
                return netatmo_connection
            # catching a type error is not strictly correct, see
            # PR: https://github.com/philippelt/netatmo-api-python/pull/100
            except (TimeoutError, TypeError) as e:
                if attempt == MAX_CONNECTION_RETRIES - 1:
                    logging.critical(
                        f"Netatmo sensor link down {e} - NO DATA BEING COLLECTED."
                    )
                else:
                    logging.info(
                        "Netatmo time-out error, waiting and establishing new connection."
                        + f"Attempt {attempt} of {MAX_CONNECTION_RETRIES}"
                    )
                    time.sleep(30)
