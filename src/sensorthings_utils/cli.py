"""SensorThings Utils CLI."""

# standard
import argparse
# external
# internal
from sensorthings_utils.sensor_things.extensions import SensorConfig
from sensorthings_utils.main import push_available

def _validate(args):
    SensorConfig(args.file)

def _push_available(args):
    push_available(
            exclude = args.exclude,
            frost_endpoint = args.frost_endpoint
            )


def main():
    parser = argparse.ArgumentParser(description="st-utils CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # subcommand: push
    push_parser = subparsers.add_parser(
            "push",
            help = "Start the stream."
            )
    push_parser.add_argument(
            "--frost-endpoint",
            help="Change default FROST server URL.",
            )
    push_parser.add_argument(
            "--exclude",
            help="Pass a list of sensor MAC addresses to exclude from the stream."
            )
    push_parser.set_defaults(func=_push_available)

    # subcommand: validate
    validate_parser = subparsers.add_parser(
            "validate",
            help = "Validate a config file."
            )
    validate_parser.add_argument("file", help="Config file to validate.")
    validate_parser.set_defaults(func=_validate)
    
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
