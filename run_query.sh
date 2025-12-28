#!/bin/bash
# Helper script to run custom queries

if [ $# -eq 0 ]; then
    echo "Usage: ./run_query.sh <query_file>"
    echo "Example: ./run_query.sh queries/drone_closures.sql"
    exit 1
fi

docker-compose run --rm notam-query python -m src.reports query "$1"