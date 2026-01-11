"""CLI command handlers."""

# standard
import os

# internal
from .menu import _setup_credentials


def _validate(args):
    """Validate sensor configuration files."""
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
    """Push available sensor data to FROST server."""
    from sensorthings_utils.main import push_available
    push_available(exclude=args.exclude, frost_endpoint=args.frost_endpoint)


def main():
    """Main CLI entry point."""
    import argparse
    
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
