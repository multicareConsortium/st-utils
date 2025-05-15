"""Test connections.py"""
#standard
import json
import os
import pytest
from pathlib import Path
from unittest import TestCase
from typing import Dict
#external
#internal
from sensorthings_utils.connections import TTSConnection, NetatmoConnection

@pytest.fixture
def tmp_credentials_dir():
   return Path(__file__).parent / ".credentials"

@pytest.fixture
def tmp_env_file():
    return Path(__file__).parent / ".env"

@pytest.fixture
def mock_tts_env_credentials():
    return {"app1":"12345qwerty", "app2":"0987asdf"}

@pytest.fixture
def tts_full_connection(
        tmp_credentials_dir: Path,
        tmp_env_file:Path,
        mock_env_credentials:Dict[str, str]
    ):
    """Initialize a TTS connection"""
    with open(tmp_env_file, "w") as f:
        env_variables = json.dumps(mock_env_credentials)
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

