#!/usr/bin/env bash
# Start the Livestream Thumbnail Generator (macOS / Linux).
# The first run sets everything up (about a minute, needs internet).
set -e
cd "$(dirname "$0")"
if [ ! -x venv/bin/python ]; then
  echo "First run: getting things ready, this takes about a minute..."
  python3 -m venv venv
  venv/bin/python -m pip install --upgrade pip >/dev/null
  venv/bin/python -m pip install -r requirements.txt
fi
if [ ! -f "$HOME/.streamlit/credentials.toml" ]; then
  mkdir -p "$HOME/.streamlit"
  printf '[general]\nemail = ""\n' > "$HOME/.streamlit/credentials.toml"
fi
exec venv/bin/python -m streamlit run app.py
