#!/usr/bin/env bash

set -o errexit

python -m pip install -r requirements.txt
python manage.py collectstatic --noinput
# Use Neon's direct endpoint for schema and bootstrap operations when supplied.
# Runtime web traffic continues to use the pooled DATABASE_URL.
MIGRATION_DATABASE_URL="${DATABASE_URL_UNPOOLED:-${DATABASE_URL:-}}"
DATABASE_URL="$MIGRATION_DATABASE_URL" python manage.py migrate --noinput
DATABASE_URL="$MIGRATION_DATABASE_URL" python manage.py bootstrap_admin
python manage.py check --deploy
