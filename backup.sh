#!/bin/bash

# Define variables
CONTAINER_NAME="wildberries_scraper_db"
DB_NAME="wildberries"
BACKUP_FILE="database_dump.sql"

export PGPASSWORD="123456"

# Run the pg_dump command inside the Docker container
docker-compose -f docker-compose.prod.yml exec $CONTAINER_NAME pg_dump -U postgres -F c $DB_NAME > $BACKUP_FILE

unset PGPASSWORD
