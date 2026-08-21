#!/usr/bin/env bash
# Launch the local VA Claims Prep app.
cd "$(dirname "$0")"
exec .venv/bin/python -m app.server
