#!/usr/bin/env bash
# Start BetSoccer Analytics locally on http://localhost:5005
# macOS / Linux launcher (equivalent of start_app.bat on Windows)

# Move to the directory this script lives in
cd "$(dirname "$0")" || exit 1

# Activate the virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

# Open the app in the default browser once the server has had a moment to start
URL="http://localhost:5005"
( sleep 3
  if command -v open >/dev/null 2>&1; then
      open "$URL"            # macOS
  elif command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$URL"        # Linux
  fi
) &

# Prefer python3 if available, otherwise fall back to python
if command -v python3 >/dev/null 2>&1; then
    python3 app.py
else
    python app.py
fi
