#!/usr/bin/env bash

set -o errexit

python -m pip install -r requirements.txt
python manage.py collectstatic --noinput
# Use Neon's direct endpoint for schema and bootstrap operations when supplied.
# Runtime web traffic continues to use the pooled DATABASE_URL.
case "${ALLOW_DEPLOY_WITHOUT_DATABASE:-false}" in
    1|true|TRUE|True|yes|YES|Yes)
        echo "Emergency degraded deployment: database build steps were skipped."
        ;;
    *)
        MIGRATION_DATABASE_URL="${DATABASE_URL_UNPOOLED:-${DATABASE_URL:-}}"
        DATABASE_URL="$MIGRATION_DATABASE_URL" python manage.py migrate --noinput
        DATABASE_URL="$MIGRATION_DATABASE_URL" python manage.py bootstrap_admin
        ;;
esac
python manage.py check --deploy
