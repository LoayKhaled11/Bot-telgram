#!/usr/bin/env bash

gunicorn app:app & python3 main.py
