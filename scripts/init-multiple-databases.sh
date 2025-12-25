#!/bin/bash
set -e

# Create langfuse database and user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER langfuse WITH PASSWORD 'langfuse_password_change_in_production';
    CREATE DATABASE langfuse OWNER langfuse;
    GRANT ALL PRIVILEGES ON DATABASE langfuse TO langfuse;
    ALTER USER langfuse CREATEDB;
EOSQL

echo "Multiple databases initialized successfully"
