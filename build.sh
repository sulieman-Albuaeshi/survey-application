#!/usr/bin/env bash
set -euo pipefail

# Build frontend assets.
npm install
npm run build

# Install Python dependencies before invoking Django commands.
python -m pip install -r requirements.txt

# Apply schema migrations first. The Sites app creates its default row after
# migrations complete, so deployment data setup must run afterwards.
python manage.py migrate --noinput
python manage.py bootstrap_deployment
python manage.py collectstatic --no-input
