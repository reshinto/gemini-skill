#!/usr/bin/env bash

python3.13 -m venv .venv
.venv/bin/pip install -r setup/requirements.txt
.venv/bin/pip install -r setup/requirements-dev.txt
