"""SensorThings Utils CLI."""

# standard
import argparse
import importlib
import inspect
import json
import logging
import os
import subprocess
from pathlib import Path
from getpass import getpass

# external
import yaml

# internal
from .paths import CREDENTIALS_DIR, TOKENS_DIR, APPLICATION_CONFIG_FILE
from .preflight.validation import validate_all_credentials
from .connections import HTTPSensorApplicationConnection, MQTTSensorApplicationConnection, SensorApplicationConnection

logger = logging.getLogger("st-utils")
logger.setLevel(logging.INFO)


def _validate(args):
    from sensorthings_utils.sensor_things.extensions import SensorConfig
    if args.file:
        validation_files = [args.file]
    else:
        validation_files = [
            os.path.join(root, f)
            for root, _, files in os.walk(".")
            for f in files
            if (f.endswith((".yaml", "yml")) and not f.startswith("template"))
        ]

    for f in validation_files:
        result, errors = SensorConfig(f).check_validity()
        if errors:
            for e in errors:
                print(e)


def _push_available(args):
    from sensorthings_utils.main import push_available
    push_available(exclude=args.exclude, frost_endpoint=args.frost_endpoint)


def _check_containers_running():
    """Check if any containers are currently running."""
    try:
        result = subprocess.run(
            ['docker', 'compose', 'ps', '-q'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


def _check_postgres_persistent_volume():
    """Check if PostgreSQL persistent volume exists."""
    try:
        result = subprocess.run(
            ['docker', 'volume', 'ls', '--format', '{{.Name}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        volumes = result.stdout.strip().split('\n')
        # Check for common volume names
        postgis_volumes = [
            v for v in volumes
            if 'postgis' in v.lower() or 'postgres' in v.lower()
        ]
        return len(postgis_volumes) > 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


def _check_existing_and_valid_credentials():
    """Check which credentials already exist and validate their structure."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Validate all credential files
    validation_results = validate_all_credentials(CREDENTIALS_DIR)
    
    existing = {
        'frost': (CREDENTIALS_DIR / "frost_credentials.json").exists() and validation_results['frost'][0],
        'postgres': (CREDENTIALS_DIR / "postgres_credentials.json").exists() and validation_results['postgres'][0],
        'mqtt': (CREDENTIALS_DIR / "mqtt_credentials.json").exists() and validation_results['mqtt'][0],
        'tomcat': (CREDENTIALS_DIR / "tomcat-users.xml").exists() and validation_results['tomcat'][0],
        'application': (CREDENTIALS_DIR / "application_credentials.json").exists() and validation_results['application'][0],
    }
    
    # Store validation results for later use
    existing['_validation_results'] = validation_results
    
    # List existing token files
    existing['tokens'] = [
        f.stem for f in TOKENS_DIR.glob("*.json")
    ] if TOKENS_DIR.exists() else []
    
    return existing

def _get_application_status():
    """
    Get status of all configured applications.
    
    Returns:
        Dictionary mapping app_name to dict with:
            - 'auth_type': 'credentials' or 'tokens'
            - 'configured': bool (whether auth is set up)
            - 'connection_class': str
    """
    app_status = {}
    
    # Read application config file
    if not APPLICATION_CONFIG_FILE.exists():
        return app_status
    
    try:
        with open(APPLICATION_CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Could not read application config: {e}")
        return app_status
    
    if not config or "applications" not in config:
        return app_status
    
    # Read application credentials if they exist
    app_creds = {}
    app_creds_file = CREDENTIALS_DIR / "application_credentials.json"
    if app_creds_file.exists():
        try:
            with open(app_creds_file, "r") as f:
                app_creds = json.load(f)
        except Exception:
            pass
    
    # Check each application
    for app_name, app_config in config["applications"].items():
        auth_type = app_config.get("authentication_type", "credentials")
        connection_class = app_config.get("connection_class", "Unknown")
        
        configured = False
        if auth_type == "credentials":
            # Check if app exists in application_credentials.json
            configured = app_name in app_creds
        elif auth_type == "tokens":
            # Check if token file exists
            token_file = TOKENS_DIR / f"{app_name}.json"
            configured = token_file.exists()
        
        app_status[app_name] = {
            "auth_type": auth_type,
            "configured": configured,
            "connection_class": connection_class,
        }
    
    return app_status


def _show_application_status():
    """Display status of all configured applications and allow setup of missing ones."""
    while True:
        app_status = _get_application_status()
        
        if not app_status:
            print("\nNo applications configured in application-configs.yml")
            return
        
        print("\n" + "=" * 50)
        print("Configured Applications")
        print("=" * 50)
        
        apps_by_auth = {"credentials": [], "tokens": []}
        unconfigured_apps = []
        
        for app_name, status in app_status.items():
            apps_by_auth[status["auth_type"]].append((app_name, status))
            if not status["configured"]:
                unconfigured_apps.append((app_name, status))
        
        # Show credentials-based apps
        if apps_by_auth["credentials"]:
            print("\n📋 Applications using Credentials:")
            for app_name, status in apps_by_auth["credentials"]:
                status_icon = "✓" if status["configured"] else "✗"
                print(f"  {status_icon} {app_name}")
                print(f"      Connection: {status['connection_class']}")
                if not status["configured"]:
                    print(f"      ⚠️  Missing in application_credentials.json")
        
        # Show token-based apps
        if apps_by_auth["tokens"]:
            print("\n🔑 Applications using Tokens:")
            for app_name, status in apps_by_auth["tokens"]:
                status_icon = "✓" if status["configured"] else "✗"
                print(f"  {status_icon} {app_name}")
                print(f"      Connection: {status['connection_class']}")
                if not status["configured"]:
                    print(f"      ⚠️  Missing token file: {app_name}.json")
        
        # Summary
        total = len(app_status)
        configured = sum(1 for s in app_status.values() if s["configured"])
        print(f"\nSummary: {configured}/{total} applications configured")
        
        # Interactive setup for unconfigured apps
        if unconfigured_apps:
            print("\n" + "=" * 50)
            print("Unconfigured Applications - Quick Setup")
            print("=" * 50)
            print("Select an application to set up (or press Enter to skip):")
            
            for i, (app_name, status) in enumerate(unconfigured_apps, 1):
                auth_type_label = "Credentials" if status["auth_type"] == "credentials" else "Token file"
                print(f"  [{i}] {app_name} ({auth_type_label})")
            print(f"  [{len(unconfigured_apps) + 1}] Skip / Back to menu")
            
            choice = input(f"\nSelect option [1-{len(unconfigured_apps) + 1}]: ").strip()
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(unconfigured_apps):
                    app_name, status = unconfigured_apps[idx]
                    
                    if status["auth_type"] == "credentials":
                        # Set up using credentials
                        if _setup_application_credentials(app_name=app_name):
                            print(f"\n✓ Successfully set up credentials for {app_name}")
                        else:
                            print(f"\n⚠️  Setup cancelled or incomplete for {app_name}")
                    else:
                        # Set up using token file
                        if _setup_token_file(token_name=app_name):
                            print(f"\n✓ Successfully set up token file for {app_name}")
                        else:
                            print(f"\n⚠️  Setup cancelled or incomplete for {app_name}")
                    
                    # Continue loop to refresh status and show remaining apps
                    continue
                elif idx == len(unconfigured_apps):
                    # Skip/Back - exit the loop
                    break
                else:
                    print("Invalid selection.")
                    continue
            except ValueError:
                # User pressed Enter or entered non-numeric - exit the loop
                break
        else:
            print("\n✓ All applications are configured!")
            break


def _check_valid_credentials(credential_file:Path) -> bool:
    """Check that mandatory credentials inlcude the right keys."""
    EXPECTED_KEYS = {
            "frost": ["frost_username", "frost_password"],
            "postgres" : ["postgres_user", "postgres_password"],
            "mqtt" : ["username", "password", "topics"],
            }



def _get_missing_mandatory(existing):
    """Get list of missing mandatory credentials."""
    mandatory = ['frost', 'postgres', 'mqtt', 'tomcat']
    return [cred for cred in mandatory if not existing.get(cred, False)]


def setup_frost_credentials():
    """Setup FROST credentials."""
    print("\n--- FROST Credentials ---")
    frost_username = input("FROST username [sta-admin]: ").strip() or "sta-admin"
    frost_password = getpass("FROST password: ")
    
    frost_creds = {
        "frost_username": frost_username,
        "frost_password": frost_password
    }
    
    frost_file = CREDENTIALS_DIR / "frost_credentials.json"
    with open(frost_file, "w") as f:
        json.dump(frost_creds, f, indent=4)
    print(f"✓ Created/Updated {frost_file}")
    return True


def _setup_postgres_credentials():
    """Setup PostgreSQL credentials."""
    print("\n--- PostgreSQL Credentials ---")
    
    # Check if persistent volume exists - CRITICAL WARNING
    has_persistent_volume = _check_postgres_persistent_volume()
    if has_persistent_volume:
        print("\n🚨 CRITICAL WARNING: PostgreSQL persistent volume detected!")
        print("   Changing the password here will LOCK YOU OUT of the database!")
        print("   The database still has the old password stored in the persistent volume.")
        print("\n   To safely change the password:")
        print("   1. Connect to the running database:")
        print("      docker compose exec database psql -U <current_user> -d sensorthings")
        print("   2. Run: ALTER USER <username> WITH PASSWORD '<new_password>';")
        print("   3. Then update postgres_credentials.json with the new password")
        print("   4. Restart containers: docker compose restart")
        print("\n   Or, if you want to start fresh (⚠️  DATA LOSS):")
        print("   docker compose down -v  # Removes volumes")
        print("   # Then run setup again")
        
        response = input("\n   Continue anyway? This may lock you out! (yes/no) [no]: ").strip().lower()
        if response != 'yes':
            print("   Skipping PostgreSQL credentials setup.")
            return False
    
    postgres_user = input("PostgreSQL user [sta-manager]: ").strip() or "sta-manager"
    postgres_password = getpass("PostgreSQL password: ")
    
    postgres_creds = {
        "postgres_user": postgres_user,
        "postgres_password": postgres_password
    }
    
    postgres_file = CREDENTIALS_DIR / "postgres_credentials.json"
    with open(postgres_file, "w") as f:
        json.dump(postgres_creds, f, indent=4)
    print(f"✓ Created/Updated {postgres_file}")
    
    if has_persistent_volume:
        print("\n⚠️  REMINDER: You must update the password in the database!")
        print("   The file has been updated, but the database still has the old password.")
        print("   See instructions above to safely change it.")
    
    return True


def _setup_mqtt_credentials():
    """Setup MQTT credentials."""
    print("\n--- MQTT Credentials ---")
    mqtt_users = {}
    
    while True:
        user_key = input("\nMQTT user key (e.g., mqtt_user_1) [press Enter to finish]: ").strip()
        if not user_key:
            break
        
        username = input(f"  Username for {user_key}: ").strip()
        password = getpass(f"  Password for {user_key}: ")
        
        topics = []
        print("  Topics (press Enter with empty name to finish):")
        while True:
            topic_name = input("    Topic name: ").strip()
            if not topic_name:
                break
            topic_perm = input(f"    Permission (read/readwrite) [read]: ").strip() or "read"
            topics.append({"name": topic_name, "perm": topic_perm})
        
        mqtt_users[user_key] = {
            "username": username,
            "password": password,
            "topics": topics
        }
    
    if mqtt_users:
        mqtt_file = CREDENTIALS_DIR / "mqtt_credentials.json"
        with open(mqtt_file, "w") as f:
            json.dump(mqtt_users, f, indent=4)
        print(f"✓ Created/Updated {mqtt_file}")
        return True
    return False


def _setup_tomcat_users():
    """Setup Tomcat users."""
    print("\n--- Tomcat Users (Webapp Authentication) ---")
    users = []
    
    while True:
        username = input("\nTomcat username [press Enter to finish]: ").strip()
        if not username:
            break
        
        password = getpass(f"  Password for {username}: ")
        roles = input(f"  Roles (comma-separated) [webapp-users]: ").strip() or "webapp-users"
        
        users.append({
            "username": username,
            "password": password,
            "roles": roles
        })
    
    if users:
        tomcat_file = CREDENTIALS_DIR / "tomcat-users.xml"
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tomcat-users xmlns="http://tomcat.apache.org/xml"
              xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
              xsi:schemaLocation="http://tomcat.apache.org/xml
              http://tomcat.apache.org/xml/tomcat-users.xsd"
              version="1.0">
'''
        for user in users:
            xml_content += f'  <user username="{user["username"]}" password="{user["password"]}" roles="{user["roles"]}"/>\n'
        xml_content += '</tomcat-users>\n'
        
        with open(tomcat_file, "w") as f:
            f.write(xml_content)
        print(f"✓ Created/Updated {tomcat_file}")
        return True
    return False


def _setup_application_credentials(app_name: str = None):
    """Setup application credentials.
    
    Args:
        app_name: Optional application name to pre-fill. If provided, only sets up this app.
    """
    print("\n--- Application Credentials ---")
    
    # Load existing credentials if file exists
    app_file = CREDENTIALS_DIR / "application_credentials.json"
    app_creds = {}
    if app_file.exists():
        try:
            with open(app_file, "r") as f:
                app_creds = json.load(f)
        except Exception:
            pass
    
    if app_name:
        # Single app mode - pre-filled, just ask for api_key
        print(f"Setting up credentials for: {app_name}")
        api_key = getpass("  API key: ").strip()
        
        if api_key:
            app_creds[app_name] = {"api_key": api_key}
            with open(app_file, "w") as f:
                json.dump(app_creds, f, indent=4)
            print(f"✓ Created/Updated {app_file}")
            return True
        return False
    else:
        # Multi-app mode - ask for application name and api_key
        print("Enter application credentials.")
        print("For each application, provide the application name and API key.")
        print("(press Enter with empty application name to finish):")
        
        new_creds = {}
        while True:
            app_name_input = input("  Application name: ").strip()
            if not app_name_input:
                break
            
            api_key = getpass(f"  API key for {app_name_input}: ").strip()
            if api_key:
                new_creds[app_name_input] = {"api_key": api_key}
        
        if new_creds:
            app_creds.update(new_creds)
            with open(app_file, "w") as f:
                json.dump(app_creds, f, indent=4)
            print(f"✓ Created/Updated {app_file}")
            return True
        return False


def _get_available_connection_classes(connection_type: str):
    """
    Get available connection classes for a given connection type.
    
    Args:
        connection_type: "http" or "mqtt"
        
    Returns:
        List of connection class names
    """
    import sensorthings_utils.connections as connections_module
    
    base_class = HTTPSensorApplicationConnection if connection_type == "http" else MQTTSensorApplicationConnection
    available_classes = []
    
    # Get all members of the connections module
    for name, obj in inspect.getmembers(connections_module):
        # Check if it's a class, ends with "Connection", and is a subclass of the base class
        if (inspect.isclass(obj) and 
            name.endswith("Connection") and 
            issubclass(obj, base_class) and 
            obj is not base_class and
            obj is not SensorApplicationConnection):
            available_classes.append(name)
    
    return sorted(available_classes)


def _add_application_to_config():
    """Add a new application to application-configs.yml."""
    print("\n--- Add Application to Config ---")
    
    # Step 1: Ask for connection type with numeric selection
    while True:
        print("\nConnection type:")
        print("  [1] HTTP")
        print("  [2] MQTT")
        choice = input("Select connection type [1-2]: ").strip()
        if choice == "1":
            connection_type = "http"
            break
        elif choice == "2":
            connection_type = "mqtt"
            break
        else:
            print("Invalid selection. Please enter 1 or 2.")
    
    # Step 2: Ask for application name
    while True:
        app_name = input("\nApplication name: ").strip()
        if app_name:
            break
        print("Application name cannot be empty. Please try again.")
    
    # Load existing config
    config = {}
    if APPLICATION_CONFIG_FILE.exists():
        try:
            with open(APPLICATION_CONFIG_FILE, "r") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error reading config file: {e}")
            return False
    else:
        # File doesn't exist, create new structure
        config = {"applications": {}}
    
    # Check if application already exists
    if "applications" in config and app_name in config["applications"]:
        overwrite = input(f"\nApplication '{app_name}' already exists. Overwrite? (yes/no) [no]: ").strip().lower()
        if overwrite != "yes":
            print("Cancelled.")
            return False
    
    # Initialize applications dict if needed
    if "applications" not in config:
        config["applications"] = {}
    
    # Build application config
    app_config = {}
    
    # Common fields - Authentication type with numeric selection
    while True:
        print("\nAuthentication type:")
        print("  [1] tokens")
        print("  [2] credentials")
        choice = input("Select authentication type [1-2]: ").strip()
        if choice == "1":
            app_config["authentication_type"] = "tokens"
            break
        elif choice == "2":
            app_config["authentication_type"] = "credentials"
            break
        else:
            print("Invalid selection. Please enter 1 or 2.")
    
    # Connection class - show available options
    available_classes = _get_available_connection_classes(connection_type)
    if not available_classes:
        print(f"\nNo {connection_type.upper()} connection classes found in connections.py")
        return False
    
    while True:
        print(f"\nAvailable {connection_type.upper()} connection classes:")
        for i, class_name in enumerate(available_classes, 1):
            print(f"  [{i}] {class_name}")
        choice = input(f"Select connection class [1-{len(available_classes)}]: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available_classes):
                app_config["connection_class"] = available_classes[idx]
                break
            else:
                print(f"Invalid selection. Please enter a number between 1 and {len(available_classes)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    if connection_type == "http":
        # HTTP-specific fields
        interval = input("\nInterval (optional, press Enter to skip): ").strip()
        if interval:
            while True:
                try:
                    app_config["interval"] = int(interval)
                    break
                except ValueError:
                    interval = input("Invalid interval value. Must be a number. Try again (or press Enter to skip): ").strip()
                    if not interval:
                        break
        
        max_retries = input("Max retries (optional, press Enter to skip): ").strip()
        if max_retries:
            while True:
                try:
                    app_config["max_retries"] = int(max_retries)
                    break
                except ValueError:
                    max_retries = input("Invalid max_retries value. Must be a number. Try again (or press Enter to skip): ").strip()
                    if not max_retries:
                        break
        
        expected_sensors = input("Expected sensors (optional, press Enter to skip): ").strip()
        if expected_sensors:
            while True:
                try:
                    app_config["expected_sensors"] = int(expected_sensors)
                    break
                except ValueError:
                    expected_sensors = input("Invalid expected_sensors value. Must be a number. Try again (or press Enter to skip): ").strip()
                    if not expected_sensors:
                        break
    
    else:  # mqtt
        # MQTT-specific fields
        max_retries = input("\nMax retries (optional, press Enter to skip): ").strip()
        if max_retries:
            while True:
                try:
                    app_config["max_retries"] = int(max_retries)
                    break
                except ValueError:
                    max_retries = input("Invalid max_retries value. Must be a number. Try again (or press Enter to skip): ").strip()
                    if not max_retries:
                        break
        
        while True:
            host = input("Host: ").strip()
            if host:
                app_config["host"] = host
                break
            print("Host is required for MQTT applications. Please try again.")
        
        port = input("Port [8883]: ").strip()
        if port:
            while True:
                try:
                    app_config["port"] = int(port)
                    break
                except ValueError:
                    port = input("Invalid port value. Must be a number. Try again: ").strip()
        else:
            app_config["port"] = 8883
        
        while True:
            topic = input("Topic: ").strip()
            if topic:
                app_config["topic"] = topic
                break
            print("Topic is required for MQTT applications. Please try again.")
        
        expected_sensors = input("Expected sensors (optional, press Enter to skip): ").strip()
        if expected_sensors:
            while True:
                try:
                    app_config["expected_sensors"] = int(expected_sensors)
                    break
                except ValueError:
                    expected_sensors = input("Invalid expected_sensors value. Must be a number. Try again (or press Enter to skip): ").strip()
                    if not expected_sensors:
                        break
    
    # Add application to config
    config["applications"][app_name] = app_config
    
    # Save config
    try:
        with open(APPLICATION_CONFIG_FILE, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False, indent=2)
        print(f"\n✓ Added '{app_name}' to {APPLICATION_CONFIG_FILE.name}")
        return True
    except Exception as e:
        print(f"Error saving config file: {e}")
        return False


def _setup_token_file(token_name: str = None):
    """Setup a new token file.
    
    Args:
        token_name: Optional token file name to pre-fill (without .json extension).
    """
    print("\n--- Token Files (Freeform JSON) ---")
    
    if token_name:
        print(f"Setting up token file for: {token_name}")
    else:
        token_name = input("Token file name (without .json extension): ").strip()
        if not token_name:
            return False
    
    print("Enter JSON key-value pairs (press Enter with empty key to finish):")
    token_data = {}
    
    while True:
        key = input("  Key: ").strip()
        if not key:
            break
        value = input(f"  Value for {key}: ").strip()
        token_data[key] = value
    
    if token_data:
        token_file = TOKENS_DIR / f"{token_name}.json"
        with open(token_file, "w") as f:
            json.dump(token_data, f, indent=4)
        print(f"✓ Created/Updated {token_file}")
        return True
    return False


def _show_main_menu(existing):
    """Show main menu and handle selections."""
    while True:
        # Get application status for summary
        app_status = _get_application_status()
        app_summary = ""
        if app_status:
            total = len(app_status)
            configured = sum(1 for s in app_status.values() if s["configured"])
            app_summary = f" ({configured}/{total} configured)"
        
        print("\n" + "=" * 50)
        print("Main Menu")
        print("=" * 50)
        print("[1] Overwrite FROST credentials" + (" ✓" if existing['frost'] else ""))
        print("[2] Overwrite PostgreSQL credentials" + (" ✓" if existing['postgres'] else ""))
        print("[3] Overwrite MQTT credentials" + (" ✓" if existing['mqtt'] else ""))
        print("[4] Overwrite Tomcat users" + (" ✓" if existing['tomcat'] else ""))
        print("[5] Add/Overwrite application credentials" + (" ✓" if existing['application'] else ""))
        print("[6] Add new token file")
        print("[7] Add application to config")
        token_status = f" ({len(existing['tokens'])} existing)" if existing['tokens'] else " (none)"
        print(f"[8] Manage existing token files{token_status}")
        print(f"[9] Show configured applications{app_summary}")
        print("[10] Exit")
        
        choice = input("\nSelect an option [10]: ").strip() or "10"
        
        if choice == "1":
            setup_frost_credentials()
            # Re-validate after update
            existing = _check_existing_and_valid_credentials()
            validation_results = existing.pop('_validation_results', {})
            if validation_results.get('frost', (False, []))[0]:
                existing['frost'] = True
            else:
                print("⚠️  Warning: File created but validation failed. Please check the file structure.")
        elif choice == "2":
            if _setup_postgres_credentials():
                # Re-validate after update
                existing = _check_existing_and_valid_credentials()
                validation_results = existing.pop('_validation_results', {})
                if validation_results.get('postgres', (False, []))[0]:
                    existing['postgres'] = True
                else:
                    print("⚠️  Warning: File created but validation failed. Please check the file structure.")
        elif choice == "3":
            if _setup_mqtt_credentials():
                # Re-validate after update
                existing = _check_existing_and_valid_credentials()
                validation_results = existing.pop('_validation_results', {})
                if validation_results.get('mqtt', (False, []))[0]:
                    existing['mqtt'] = True
                else:
                    print("⚠️  Warning: File created but validation failed. Please check the file structure.")
        elif choice == "4":
            if _setup_tomcat_users():
                # Re-validate after update
                existing = _check_existing_and_valid_credentials()
                validation_results = existing.pop('_validation_results', {})
                if validation_results.get('tomcat', (False, []))[0]:
                    existing['tomcat'] = True
                else:
                    print("⚠️  Warning: File created but validation failed. Please check the file structure.")
        elif choice == "5":
            if _setup_application_credentials():
                # Re-validate after update
                existing = _check_existing_and_valid_credentials()
                validation_results = existing.pop('_validation_results', {})
                if validation_results.get('application', (False, []))[0]:
                    existing['application'] = True
                else:
                    print("⚠️  Warning: File created but validation failed. Please check the file structure.")
        elif choice == "6":
            if _setup_token_file():
                existing = _check_existing_and_valid_credentials()  # Refresh token list
                existing.pop('_validation_results', None)  # Remove validation results
        elif choice == "7":
            _add_application_to_config()
        elif choice == "8":
            _manage_tokens(existing['tokens'])
            existing = _check_existing_and_valid_credentials()  # Refresh token list
            existing.pop('_validation_results', None)  # Remove validation results
        elif choice == "9":
            _show_application_status()
            input("\nPress Enter to continue...")
        elif choice == "10":
            print("\nExiting setup.")
            break
        else:
            print("Invalid option. Please try again.")


def _manage_tokens(existing_tokens):
    """Manage existing token files."""
    if not existing_tokens:
        print("\nNo existing token files found.")
        return
    
    print("\n--- Manage Token Files ---")
    print("Existing token files:")
    for i, token in enumerate(existing_tokens, 1):
        print(f"  [{i}] {token}.json")
    print(f"  [{len(existing_tokens) + 1}] Back to main menu")
    
    choice = input(f"\nSelect token to overwrite [1-{len(existing_tokens) + 1}]: ").strip()
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(existing_tokens):
            token_name = existing_tokens[idx]
            print(f"\nOverwriting {token_name}.json")
            print("Enter JSON key-value pairs (press Enter with empty key to finish):")
            token_data = {}
            
            while True:
                key = input("  Key: ").strip()
                if not key:
                    break
                value = input(f"  Value for {key}: ").strip()
                token_data[key] = value
            
            if token_data:
                token_file = TOKENS_DIR / f"{token_name}.json"
                with open(token_file, "w") as f:
                    json.dump(token_data, f, indent=4)
                print(f"✓ Updated {token_file}")
        elif idx == len(existing_tokens):
            return  # Back to main menu
        else:
            print("Invalid selection.")
    except ValueError:
        print("Invalid input. Please enter a number.")


def _setup_credentials(args):
    """Interactive setup for credential files with menu system."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("SensorThings Utils Credential Setup")
    print("=" * 50)
    
    # Check if containers are running and warn
    containers_running = _check_containers_running()
    if containers_running:
        print("\n⚠️  WARNING: Containers are currently running!")
        print("   Credential changes will NOT take effect until containers are restarted.")
        print("   After setup, run: docker compose restart")
        print()
    
    # Check existing credentials and validate them
    existing = _check_existing_and_valid_credentials()
    validation_results = existing.pop('_validation_results', {})
    
    # Check for invalid credential files and prompt user to fix them
    invalid_files = []
    for cred_type, (is_valid, errors) in validation_results.items():
        file_exists = {
            'frost': (CREDENTIALS_DIR / "frost_credentials.json").exists(),
            'postgres': (CREDENTIALS_DIR / "postgres_credentials.json").exists(),
            'mqtt': (CREDENTIALS_DIR / "mqtt_credentials.json").exists(),
            'tomcat': (CREDENTIALS_DIR / "tomcat-users.xml").exists(),
            'application': (CREDENTIALS_DIR / "application_credentials.json").exists(),
        }.get(cred_type, False)
        
        if file_exists and not is_valid:
            invalid_files.append((cred_type, errors))
    
    if invalid_files:
        print("\n⚠️  WARNING: Some credential files have validation errors!")
        print("=" * 50)
        for cred_type, errors in invalid_files:
            print(f"\n❌ Invalid {cred_type.upper()} credentials:")
            for error in errors:
                print(f"   {error}")
        
        print("\n" + "=" * 50)
        response = input("\nWould you like to fix these files now? (yes/no) [yes]: ").strip().lower()
        if response != 'no':
            print("\nFixing invalid credential files...\n")
            for cred_type, _ in invalid_files:
                if cred_type == 'frost':
                    setup_frost_credentials()
                    existing['frost'] = True
                elif cred_type == 'postgres':
                    if _setup_postgres_credentials():
                        existing['postgres'] = True
                elif cred_type == 'mqtt':
                    if _setup_mqtt_credentials():
                        existing['mqtt'] = True
                elif cred_type == 'tomcat':
                    if _setup_tomcat_users():
                        existing['tomcat'] = True
                elif cred_type == 'application':
                    if _setup_application_credentials():
                        existing['application'] = True
            
            # Re-validate after fixing
            existing = _check_existing_and_valid_credentials()
            validation_results = existing.pop('_validation_results', {})
            print("\n✓ Validation complete. Re-checking files...")
            
            # Check if any files are still invalid
            still_invalid = [
                cred_type for cred_type, (is_valid, _) in validation_results.items()
                if not is_valid and {
                    'frost': (CREDENTIALS_DIR / "frost_credentials.json").exists(),
                    'postgres': (CREDENTIALS_DIR / "postgres_credentials.json").exists(),
                    'mqtt': (CREDENTIALS_DIR / "mqtt_credentials.json").exists(),
                    'tomcat': (CREDENTIALS_DIR / "tomcat-users.xml").exists(),
                    'application': (CREDENTIALS_DIR / "application_credentials.json").exists(),
                }.get(cred_type, False)
            ]
            
            if still_invalid:
                print(f"⚠️  Warning: Some files are still invalid: {', '.join(still_invalid)}")
                print("   You may need to fix them manually or try again.")
        else:
            print("Skipping validation fixes. You can fix them later from the main menu.")
    
    # Handle legacy command-line flags (for backward compatibility)
    if any([args.all, args.frost, args.postgres, args.mqtt, args.tomcat, args.token]):
        # Legacy mode: use flags
        if args.frost or args.all:
            setup_frost_credentials()
        if args.postgres or args.all:
            _setup_postgres_credentials()
        if args.mqtt or args.all:
            _setup_mqtt_credentials()
        if args.tomcat or args.all:
            _setup_tomcat_users()
        if args.token or args.all:
            _setup_token_file()
        
        # Validate all created/updated files
        print("\n" + "=" * 50)
        print("Validating credential files...")
        validation_results = validate_all_credentials(CREDENTIALS_DIR)
        
        all_valid = True
        for cred_type, (is_valid, errors) in validation_results.items():
            file_exists = {
                'frost': (CREDENTIALS_DIR / "frost_credentials.json").exists(),
                'postgres': (CREDENTIALS_DIR / "postgres_credentials.json").exists(),
                'mqtt': (CREDENTIALS_DIR / "mqtt_credentials.json").exists(),
                'tomcat': (CREDENTIALS_DIR / "tomcat-users.xml").exists(),
                'application': (CREDENTIALS_DIR / "application_credentials.json").exists(),
            }.get(cred_type, False)
            
            if file_exists:
                if is_valid:
                    print(f"✓ {cred_type.upper()} credentials: Valid")
                else:
                    all_valid = False
                    print(f"❌ {cred_type.upper()} credentials: Invalid")
                    for error in errors:
                        print(f"   {error}")
        
        print("\n" + "=" * 50)
        if all_valid:
            print("Setup complete! All credential files are valid.")
        else:
            print("Setup complete, but some files have validation errors.")
            print("Please fix the errors above or run 'stu setup' again to fix them.")
        return
    
    # New interactive menu mode
    # Step 1: Handle missing mandatory credentials
    missing = _get_missing_mandatory(existing)
    
    if missing:
        print(f"\n⚠️  Missing mandatory credentials: {', '.join(missing)}")
        print("Setting up missing mandatory credentials first...\n")
        
        for cred_type in missing:
            if cred_type == 'frost':
                setup_frost_credentials()
            elif cred_type == 'postgres':
                _setup_postgres_credentials()
            elif cred_type == 'mqtt':
                _setup_mqtt_credentials()
            elif cred_type == 'tomcat':
                _setup_tomcat_users()
        
        # Re-validate after creating missing credentials
        existing = _check_existing_and_valid_credentials()
        validation_results = existing.pop('_validation_results', {})
        
        # Check if any created files are invalid
        invalid_created = []
        for cred_type in missing:
            if cred_type in validation_results:
                is_valid, errors = validation_results[cred_type]
                file_exists = {
                    'frost': (CREDENTIALS_DIR / "frost_credentials.json").exists(),
                    'postgres': (CREDENTIALS_DIR / "postgres_credentials.json").exists(),
                    'mqtt': (CREDENTIALS_DIR / "mqtt_credentials.json").exists(),
                    'tomcat': (CREDENTIALS_DIR / "tomcat-users.xml").exists(),
                }.get(cred_type, False)
                
                if file_exists:
                    if is_valid:
                        existing[cred_type] = True
                    else:
                        invalid_created.append((cred_type, errors))
        
        if invalid_created:
            print("\n⚠️  Warning: Some credential files were created but have validation errors:")
            for cred_type, errors in invalid_created:
                print(f"\n❌ {cred_type.upper()} credentials:")
                for error in errors:
                    print(f"   {error}")
            print("\nYou can fix these from the main menu.")
    
    # Step 2: Show main menu
    _show_main_menu(existing)


def main():
    parser = argparse.ArgumentParser(description="st-utils CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # subcommand: push
    push_parser = subparsers.add_parser("push", help="Start the stream.")
    push_parser.add_argument(
        "--frost-endpoint",
        help="Change default FROST server URL.",
    )
    push_parser.add_argument(
        "--exclude",
        help="Pass a list of sensor MAC addresses to exclude from the stream.",
    )
    push_parser.set_defaults(func=_push_available)

    # subcommand: validate
    validate_parser = subparsers.add_parser(
        "validate", help="Validate all yaml files in the working directory."
    )
    validate_parser.add_argument(
        "file", nargs="?", default=None, help="Config file to validate."
    )
    validate_parser.set_defaults(func=_validate)

    # subcommand: setup
    setup_parser = subparsers.add_parser(
        "setup", help="Interactive setup for credential files."
    )
    setup_parser.add_argument(
        "--all", action="store_true", help="Setup all credential types."
    )
    setup_parser.add_argument(
        "--frost", action="store_true", help="Setup FROST credentials."
    )
    setup_parser.add_argument(
        "--postgres", action="store_true", help="Setup PostgreSQL credentials."
    )
    setup_parser.add_argument(
        "--mqtt", action="store_true", help="Setup MQTT credentials."
    )
    setup_parser.add_argument(
        "--tomcat", action="store_true", help="Setup Tomcat users (webapp authentication)."
    )
    setup_parser.add_argument(
        "--token", action="store_true", help="Setup a token file (freeform JSON)."
    )
    setup_parser.set_defaults(func=_setup_credentials)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
