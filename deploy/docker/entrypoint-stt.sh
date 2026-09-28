#!/bin/sh
set -eu
cd /app
mkdir -p /app/data "$HF_HOME"
exec "$@"
