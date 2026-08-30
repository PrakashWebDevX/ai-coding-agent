#!/usr/bin/env bash
# Runs the FastAPI backend and Streamlit frontend together for local dev.
set -euo pipefail

trap 'kill 0' EXIT

uv run uvicorn backend.main:app --reload --port 8000 &
sleep 2
uv run streamlit run frontend/streamlit_app.py

wait
