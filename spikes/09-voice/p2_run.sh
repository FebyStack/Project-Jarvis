#!/bin/sh
# .venv/bin/python, not `uv run`: uv would try to re-resolve the en_core_web_sm URL through the dead proxy.
cd "$(dirname "$0")/../.." && HF_HUB_OFFLINE=1 HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 .venv/bin/python spikes/09-voice/p2_offline.py
