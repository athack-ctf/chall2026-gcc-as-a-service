#!/usr/bin/env bash

set -e

# Ensure tmp directory exists
mkdir -p ./tmp

# Compile fake flag source into ./tmp/echo-flag
gcc ./echo-flag-src/echo-fake-flag.c -o ./tmp/echo-flag

# Add ./tmp to PATH for this session
export PATH="$(pwd)/tmp:$PATH"

# Run the app
exec python app.py
