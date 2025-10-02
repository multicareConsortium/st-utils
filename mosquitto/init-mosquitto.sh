#!/bin/sh
set -e

PASSWORD_FILE=/mosquitto/config/passwords.txt
rm -f "$PASSWORD_FILE"

if [ -n "$MQTT_USERS" ]; then
    echo "Generating Mosquitto users..."
    IFS=',' # split on commas
    for pair in $MQTT_USERS; do
        IFS='=' read -r username password <<EOF
$pair
EOF
        mosquitto_passwd -b -c "$PASSWORD_FILE" "$username" "$password"
    done
fi

chown mosquitto:mosquitto $PASSWORD_FILE
echo "Starting Mosquitto..."
exec mosquitto -c /mosquitto/config/mosquitto.conf

