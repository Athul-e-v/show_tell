#!/usr/bin/env bash
set -e

cd /home/jothiswaranoh5717/show_tell/api

exec .venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000
