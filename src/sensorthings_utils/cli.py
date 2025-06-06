"""SensorThings Utils CLI."""

# standard
import argparse
# external
# internal
from sensorthings_utils.sensor_things.extensions import SensorConfig

def validate(args):
    SensorConfig(args.file)

def main():
    parser = argparse.ArgumentParser(description="st-utils CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # subcommand: validate
    validate_parser = subparsers.add_parser(
            "validate",
            help = "Validate a config file."
            )
    validate_parser.add_argument("file", help="Config file to validate.")
    validate_parser.set_defaults(func=validate)
    
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
