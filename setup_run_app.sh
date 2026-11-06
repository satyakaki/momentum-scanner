#!/usr/bin/env bash
set -e

INSTRUMENTS_URL="https://api.kite.trade/instruments"
INSTRUMENTS_FILE="data/instruments.csv"

unset SSL_CERT_FILE REQUESTS_CA_BUNDLE CURL_CA_BUNDLE

mkdir -p data

if [ -f "$INSTRUMENTS_FILE" ]; then
    echo "instruments file is present in data folder"
else
    echo "Downloading instruments file to base folder..."
    rm -f instruments.csv
    if command -v wget >/dev/null 2>&1; then
        wget --no-check-certificate -O instruments.csv "$INSTRUMENTS_URL"
    elif command -v curl >/dev/null 2>&1; then
        curl -k -L --fail -o instruments.csv "$INSTRUMENTS_URL"
    else
        echo "Error: neither wget nor curl is installed; cannot download instruments file." >&2
        exit 1
    fi

    echo "Moving instruments.csv to data folder..."
    mv instruments.csv data/instruments.csv
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
else
    echo "Using existing virtual environment..."
fi

source .venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Starting app on port 8000..."
uvicorn app:app --host 0.0.0.0 --port 8000

