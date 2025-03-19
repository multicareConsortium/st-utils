# the PostgreSQL database spun up by the docker-compose requires a first time 
# initialization of a USERS and USER_ROLES table required for basic authorization.

#!/bin/bash

set -e
# this is the default entry point for the image
/usr/local/bin/docker-entrypoint.sh postgres &
# brief wait untill PG is ready:
until pg_isready -h database -U sensorthings -d sensorthings; do
    echo "Waiting for PostgreSQL to be ready"
    sleep 10
done
# first auth attempt triggers FROST to create the Basic Auth tables:
wget --header="Authorization: Basic $(echo -n 'username:password' | base64)" http://web:8080/FROST-Server/v1.1/Datastreams
# change admin, write and read passwords:
psql -U sensorthings -d sensorthings <<EOF

-- Update password for existing users (example: admin)
UPDATE "USERS"
SET "USER_PASS" = '${POSTGRES_PASSWORD}'
WHERE "USER_NAME" IN ('admin', 'write', 'read');

EOF

echo "Database initialization complete."

wait $!