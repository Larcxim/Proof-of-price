#!/bin/bash
set -e
cd "$(dirname "$0")"

if [ -z "${OC_API_KEY:-}" ] || [ -z "${OC_SECRET_KEY:-}" ]; then
  echo "Proof of Price — private, read-only live API session"
  echo "Credentials are used only by the local server and are not saved by this script."
  read -r -s -p "Web3 API Key (hidden): " OC_API_KEY
  echo
  read -r -s -p "Web3 Secret Key (hidden): " OC_SECRET_KEY
  echo
  export OC_API_KEY OC_SECRET_KEY
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found. Install Python 3, then double-click this file again."
  read -r -p "Press Return to close... " _
  exit 1
fi

echo "Starting the local dashboard at http://127.0.0.1:8000"
echo "Open that address in your browser. Keep this Terminal window open."
echo "Press Control-C here to stop the server."
exec python3 serve.py --host 127.0.0.1 --port 8000
