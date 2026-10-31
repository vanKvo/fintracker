#!/bin/sh
# Creates the Ledger's database on the first start of the volume. The Knowledge database is the container's POSTGRES_DB,
# and its roles come from Knowledge's own init script, mounted beside this one (see docker-compose.yml).
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE fintracker"
