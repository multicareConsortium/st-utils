#!/bin/sh

export persistence_db_username=$(awk -F'"' '/"postgres_user"/ {print $4}' /run/secrets/postgres_credentials)
export persistence_db_password=$(awk -F'"' '/"postgres_password"/ {print $4}' /run/secrets/postgres_credentials)

/usr/local/tomcat/bin/catalina.sh run
