#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Websupport DNS addon..."
exec python3 -u /app/run.py
