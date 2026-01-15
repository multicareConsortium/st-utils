#!/bin/sh
set -e

# Set up FROST persistence credentials (from init-frost.sh)
export persistence_db_username=$(awk -F'"' '/"postgres_user"/ {print $4}' /run/secrets/postgres_credentials)
export persistence_db_password=$(awk -F'"' '/"postgres_password"/ {print $4}' /run/secrets/postgres_credentials)

# Set up FROST auth credentials if frost_credentials secret exists (from init-auth-frost.sh)
if [ -f "/run/secrets/frost_credentials" ]; then
    export auth_db_username=$(awk -F'"' '/"frost_username"/ {print $4}' /run/secrets/frost_credentials)
    export auth_db_password=$(awk -F'"' '/"frost_password"/ {print $4}' /run/secrets/frost_credentials)
fi

# Handle tomcat-users.xml for public access
# If the mounted file is empty or only contains the root element (no users),
# Tomcat will treat it as public access (no authentication required)
if [ -f "/usr/local/tomcat/conf/tomcat-users.xml" ]; then
    # Check if file is empty or only has root element (no <user> tags)
    if ! grep -q '<user ' /usr/local/tomcat/conf/tomcat-users.xml; then
        echo "No users found in tomcat-users.xml - application will be publicly accessible"
        # Note: We cannot remove the file as it's a mounted volume, but Tomcat
        # will treat an empty/minimal tomcat-users.xml as no authentication
    fi
fi

# Start Tomcat
exec /usr/local/tomcat/bin/catalina.sh run