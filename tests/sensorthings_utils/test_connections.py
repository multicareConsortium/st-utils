"""Test connections.py"""
#standard
import json
import logging
import os
import pytest
from pathlib import Path
from unittest import TestCase
from typing import Dict
import time
#external
#internal
from sensorthings_utils.connections import _init_credentials, TTSConnection, NetatmoConnection

# Common Fixtures
@pytest.fixture
def tmp_credentials_dir(tmp_path):
   time.sleep(1)
   return tmp_path / ".credentials"

@pytest.fixture
def mock_tts_env_credentials():
    return {"app1":"12345qwerty", "app2":"0987asdf"}

@pytest.fixture
def mock_netatmo_credentials():
    return {"NETATMO_CLIENT_ID": "1", "NETATMO_CLIENT_SECRET": "2", "NETATMO_REFRESH_TOKEN": "3"}

@pytest.fixture
def mock_env_file(
        tmp_path,
        mock_tts_env_credentials,
        mock_netatmo_credentials
        ):
    tmp_env_file = tmp_path / ".env"
    tts_json = json.dumps(mock_tts_env_credentials)
    netatmo_json = json.dumps(mock_netatmo_credentials)
    with open(tmp_env_file, "a") as f:
        f.write(f"TTS_CREDENTIALS={tts_json}\n" )
        f.write(f"NETATMO_CREDENTIALS={netatmo_json}\n")
    return tmp_env_file

@pytest.fixture
def tts_full_connection(
        tmp_credentials_dir: Path,
        tmp_env_file:Path,
        mock_env_file:Dict[str, str]
    ):
    """Initialize a TTS connection"""
    with open(tmp_env_file, "w") as f:
        env_variables = json.dumps(mock_env_file)
        f.write(f"TTS_CREDENTIALS={env_variables}")
    tts_connection = TTSConnection(
            credentials_dir=tmp_credentials_dir, env_file=tmp_env_file,
            application_name="app1", mqtt_host="placeholder"
    )
    yield tts_connection
    try:
        os.rmdir(tmp_credentials_dir)
        os.remove(tmp_env_file)
    except:
        pass

class TestInitCredentials:

    def test_init_credentials_newer_env(self, tmp_credentials_dir, mock_env_file):
        """Create credentials from a newer .env file."""
        now = time.time()
        # add some time to make sure the env_file is newer than the credentials.
        os.utime(mock_env_file, (now +10, now+10))
        credentials_file = _init_credentials(
                "netatmo",
                target=tmp_credentials_dir, 
                env=mock_env_file, 
                container_environment=False
            )
        assert credentials_file.exists()
        with open(credentials_file, "r") as f:
            credential_lines = f.readlines()
            for line in credential_lines:
                assert line
                assert len(credential_lines) == 1
                dict_creds = json.loads(line)
                assert "NETATMO_CLIENT_ID" in dict_creds
                assert "NETATMO_CLIENT_SECRET" in dict_creds
                assert "NETATMO_REFRESH_TOKEN" in dict_creds


def test_tts_init(tts_full_connection):
    assert isinstance(tts_full_connection, TTSConnection)

def test_tts_credential_path(tts_full_connection: TTSConnection):
    """Should be able to create a credential file from scratch."""
    assert isinstance(tts_full_connection._credentials, Path)
    assert tts_full_connection._credentials == Path(__file__).parent / ".credentials" / ".tts.credentials"
    assert tts_full_connection.env_file == Path(__file__).parent / ".env"

def test_tts_credential_writing(tts_full_connection: TTSConnection):
    with open(tts_full_connection._credentials, "r") as f:
        assert json.load(f) == {"app1":"12345qwerty", "app2":"0987asdf"}

