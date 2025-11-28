#!/bin/bash
# Run all database migrations

echo "Running database migrations..."

# Migration 1: Add environment to robot_configs
if [ -f "migrate_add_environment.py" ]; then
    echo "Running robot_configs.environment migration..."
    python migrate_add_environment.py || echo "Migration may already be applied"
fi

# Migration 2: Add environment to api_credentials
if [ -f "migrate_add_environment_to_api_credentials.py" ]; then
    echo "Running api_credentials.environment migration..."
    python migrate_add_environment_to_api_credentials.py || echo "Migration may already be applied"
fi

echo "✅ All migrations completed!"

