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
   return tmp_path / ".credentials"

@pytest.fixture
def tmp_env_file(tmp_path):
    return tmp_path / ".env"

@pytest.fixture
def mock_tts_credentials():
    """TTS credentials as loaded from a .env file."""
    return {"app1":"12345qwerty", "app2":"0987asdf"}

@pytest.fixture
def mock_netatmo_credentials():
    """Netatmo credentials as loaded from a .env file."""
    return {"CLIENT_ID": "1", "CLIENT_SECRET": "2", "REFRESH_TOKEN": "3"}

@pytest.fixture
def bad_credentials():
    """Bad credentials."""
    return {"qwerty":123}

@pytest.fixture
def mock_env_file(
        tmp_path,
        mock_tts_credentials,
        mock_netatmo_credentials
        ):
    tmp_env_file = tmp_path / ".env"
    tts_json = json.dumps(mock_tts_credentials)
    netatmo_json = json.dumps(mock_netatmo_credentials)
    with open(tmp_env_file, "a") as f:
        f.write(f"TTS_CREDENTIALS={tts_json}\n" )
        f.write(f"NETATMO_CREDENTIALS={netatmo_json}\n")
    return tmp_env_file

@pytest.fixture
def bad_env_file(
        tmp_path,
        bad_credentials,
        ):
    """An .env file populated with garbage credentials."""
    tmp_env_file = tmp_path / ".env"
    bad_creds_json = json.dumps(bad_credentials)
    with open(tmp_env_file, "a") as f:
        f.write(f"TTS_CREDENTIALS={bad_creds_json}\n" )
        f.write(f"NETATMO_CREDENTIALS={bad_creds_json}\n")
    return tmp_env_file

@pytest.fixture
def empty_env_file(
        tmp_env_file
        ):
    """An empty .env file"""
    return tmp_env_file

class TestTTSConnection():

    def test_make_mock_connection(self):
        """Should make a TTS Connection (no auth.)"""
        tts_connection = TTSConnection(
                application_name = "app1",
                mqtt_host = "mock.host"
                )
        assert isinstance(tts_connection, TTSConnection)

    @pytest.mark.slow
    def test_real_tts_connection(self):
        """
        Integration test that tests out a real connection with an active system.

        For this test to pass you will need to have real credentials in the
        .env or .../.credentials/.tts.credentials
        """
        # we need a small monkeypatch here to get the application name from
        # the available credentials in your real .env.
        tts_credentials = _init_credentials(sensor_type = "tts")
        with open(tts_credentials, "r") as f:
            credentials = json.loads(f.read())
            application_name = next(iter(credentials))
        
        tts_connection = TTSConnection(
                application_name=application_name,
                mqtt_host = "eu1.cloud.thethings.network",
                )
        tts_connection.subscribe()
        payload = tts_connection.retrieve()
        logging.debug(f"{payload}")
        time.sleep(5)
        assert isinstance(payload, dict)
        assert payload != None
        assert "end_device_ids" in payload
        
class TestInitCredentials:
    """Testing the _init_credentials function."""
    def test_init_credentials_newer_env(self, tmp_credentials_dir, mock_env_file):
        """Should create credentials from a newer .env file."""
        now = time.time()
        # add some time to make sure the env_file is newer than the credentials.
        os.utime(mock_env_file, (now +10, now+10))
        credentials_file = _init_credentials(
                "netatmo",
                target=tmp_credentials_dir, 
                env=mock_env_file, 
            )
        assert credentials_file.exists()
        with open(credentials_file, "r") as f:
            credential_lines = f.readlines()
            for line in credential_lines:
                assert line
                assert len(credential_lines) == 1
                dict_creds = json.loads(line)
                assert "CLIENT_ID" in dict_creds
                assert "CLIENT_SECRET" in dict_creds
                assert "REFRESH_TOKEN" in dict_creds

    def test_exception_missing_env_variables(self, tmp_credentials_dir, tmp_path, monkeypatch):
        """Should raise an error if the credentials file is new but no environment variables where found."""
        with pytest.raises(FileNotFoundError, match="No credentials found"):
            monkeypatch.delenv("NETATMO_CREDENTIALS")
            credentials_file = _init_credentials(
                    "netatmo",
                    target=tmp_credentials_dir,
                    env=tmp_path / ".env",
            )

    def test_exception_missing_creds_from_env_and_credentials_exist(self, tmp_credentials_dir, empty_env_file, monkeypatch):
        """Should raise an error if bad or missing credentials are found."""
        # need the credentials dir and file to pre-exist for this test
        credentials_dir = tmp_credentials_dir
        credentials_dir.mkdir()
        (credentials_dir / ".netatmo.credentials").touch()
        # add some time to make sure the env_file is newer than the credentials.
        now = time.time()
        monkeypatch.delenv("NETATMO_CREDENTIALS")
        with pytest.raises(ValueError, match="Ensure key is in .env file!"):
            credentials_file = _init_credentials(
                    "netatmo",
                    target=tmp_credentials_dir,
                    env=empty_env_file,
            )
                
    def test_container_environment(
            self, 
            tmp_credentials_dir, 
            tmp_env_file,
            mock_netatmo_credentials, 
            monkeypatch,
            ):
        """Should load up variables from the environment and write them to a credential file"""
        monkeypatch.setenv("NETATMO_CREDENTIALS", json.dumps(mock_netatmo_credentials))
        credentials_file = _init_credentials(
                "netatmo",
                target = tmp_credentials_dir,
                env=tmp_env_file,
                )
        assert credentials_file.exists()
        with open(credentials_file, "r") as f:
            credential_lines = f.readlines()
            for line in credential_lines:
                assert line
                assert len(credential_lines) == 1
                dict_creds = json.loads(line)
                assert "CLIENT_ID" in dict_creds
                assert "CLIENT_SECRET" in dict_creds
                assert "REFRESH_TOKEN" in dict_creds

class TestNetatmoConnection:

    def test_make_mock_connection(self):
            """Should make a Netatmo Connection (no auth.)"""
            netatmo_connection = NetatmoConnection()
            assert isinstance(netatmo_connection, NetatmoConnection)

    def test_exception_for_bad_credentials(self, tmp_credentials_dir, bad_env_file):
        """Should raise exception for bad credentials."""
        init_bad_env_file = bad_env_file
        # make sure env file is newer so it is used (not artifact creds)
        now = time.time()
        os.utime(init_bad_env_file, (now+10, now+10)) 
        netatmo_connect = NetatmoConnection(tmp_credentials_dir, bad_env_file)
        with pytest.raises(
                AttributeError, match=r"Netatmo credentials in wrong format!"
            ):
            netatmo_connect._credentials

    @pytest.mark.slow
    def test_real_netatmo_connection(self, caplog):
        """
        Integration test that tests out a real netatmo connection with an active system.

        For this test to pass you will need to have real credentials in the
        .env or .../.credentials/.netatmo.credentials
        """
        from logging import ERROR
        # this test might not always work because lnetatmo tokens get stale
        # sometimes, we capture the logs.
        with caplog.at_level(ERROR, logger="lnetatmo"):
            netatmo_connection = NetatmoConnection(max_retries=1)
            payload = netatmo_connection.retrieve()
            if any("invalid_grant" in msg for msg in caplog.messages):
                pytest.skip(
                        "Test skipped because Netatmo Grant Token is stale. " +
                        "Update token to re-try test."
                        )
            assert isinstance(payload, list)
            assert payload != None

